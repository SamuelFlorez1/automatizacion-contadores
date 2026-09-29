"""Pipeline común de ingesta: dedupe → rate limit → guardar original → extraer → persistir.

Todos los canales (upload, WhatsApp, email) terminan aquí. Reglas:
- Idempotente: `documents.dedupe_key` = sha256 del contenido, único por despacho.
- El archivo original se guarda ANTES de extraer; si la extracción falla queda status='error'.
"""

from __future__ import annotations

import mimetypes
import re
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any, Literal
from zoneinfo import ZoneInfo

import structlog
from postgrest.exceptions import APIError
from supabase import Client

from app.config import get_settings
from app.db.client import get_service_client
from app.extraction.schemas import ExtractedInvoice, ExtractionError
from app.extraction.validators import dedupe_key, normalize_nit
from app.extraction.vision import IMAGE_MIMES, PDF_MIME, extract_invoice_vision
from app.extraction.xml_ubl import parse_ubl_invoice

log = structlog.get_logger()

Source = Literal["whatsapp", "email", "upload"]
Outcome = Literal["parsed", "duplicate", "error", "stored", "rate_limited", "rejected"]

XML_MIMES = {"application/xml", "text/xml"}
CSV_MIMES = {"text/csv", "application/csv", "application/vnd.ms-excel"}


class IngestRejected(Exception):
    """Rechazo antes de crear documento (tamaño, rate limit)."""

    def __init__(self, outcome: Outcome, detail: str):
        super().__init__(detail)
        self.outcome = outcome
        self.detail = detail


@dataclass
class IngestResult:
    outcome: Outcome
    document_id: str | None = None
    invoice_id: str | None = None
    detail: str | None = None
    warnings: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ helpers
def guess_mime(filename: str | None, declared: str | None, content: bytes) -> str:
    if content[:5] == b"%PDF-":
        return PDF_MIME
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if content[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    head = content[:200].lstrip(b"\xef\xbb\xbf \r\n\t")
    if head.startswith(b"<?xml") or head.startswith(b"<Invoice"):
        return "application/xml"
    if declared and declared != "application/octet-stream":
        return declared.split(";")[0].strip().lower()
    return mimetypes.guess_type(filename or "")[0] or "application/octet-stream"


def doc_kind(mime: str, filename: str | None) -> str:
    if mime in XML_MIMES:
        return "invoice_xml"
    if mime == PDF_MIME:
        return "invoice_pdf"
    if mime in IMAGE_MIMES:
        return "invoice_image"
    if mime in CSV_MIMES or (filename or "").lower().endswith(".csv"):
        return "bank_statement"
    return "other"


def _safe_name(name: str | None) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name or "archivo")[:120]


def find_client(db: Client, *, phone: str | None = None, email: str | None = None) -> dict | None:
    """Identifica cliente por teléfono (últimos 10 dígitos) o email."""
    if phone:
        tail = re.sub(r"\D", "", phone)[-10:]
        if len(tail) == 10:
            rows = db.table("clients").select("id, firm_id, nit, phone").execute().data
            for r in rows:
                if r.get("phone") and re.sub(r"\D", "", r["phone"])[-10:] == tail:
                    return r
    if email:
        rows = db.table("clients").select("id, firm_id, nit, email").ilike("email", email.strip()).execute().data
        if rows:
            return rows[0]
    return None


def _ensure_bucket(db: Client, bucket: str) -> None:
    try:
        db.storage.get_bucket(bucket)
    except Exception:
        try:
            db.storage.create_bucket(bucket, options={"public": False})
        except Exception as e:  # carrera con otro worker: ya existe
            log.warning("bucket_create_failed", error=str(e))


def _check_rate_limit(db: Client, client_id: str) -> None:
    s = get_settings()
    tz = ZoneInfo(s.default_timezone)
    start = datetime.combine(datetime.now(tz).date(), time.min, tzinfo=tz)
    res = (
        db.table("documents")
        .select("id", count="exact")
        .eq("client_id", client_id)
        .gte("received_at", start.isoformat())
        .execute()
    )
    if (res.count or 0) >= s.ingest_max_docs_per_client_day:
        raise IngestRejected(
            "rate_limited",
            f"Límite diario de {s.ingest_max_docs_per_client_day} documentos alcanzado para este cliente",
        )


# ------------------------------------------------------------------ pipeline
def ingest_document(
    *,
    client: dict,
    source: Source,
    content: bytes,
    filename: str | None,
    declared_mime: str | None = None,
    channel_ref: str | None = None,
    db: Client | None = None,
) -> IngestResult:
    db = db or get_service_client()
    s = get_settings()
    firm_id, client_id = client["firm_id"], client["id"]

    if not content:
        raise IngestRejected("rejected", "Archivo vacío")
    if len(content) > s.ingest_max_file_bytes:
        raise IngestRejected("rejected", f"Archivo supera {s.ingest_max_file_bytes // (1024 * 1024)} MB")

    key = dedupe_key(content)
    existing = db.table("documents").select("id, status").eq("firm_id", firm_id).eq("dedupe_key", key).execute().data
    if existing:
        return IngestResult("duplicate", document_id=existing[0]["id"], detail="Documento ya recibido")

    _check_rate_limit(db, client_id)

    mime = guess_mime(filename, declared_mime, content)
    kind = doc_kind(mime, filename)
    path = f"{firm_id}/{client_id}/{key}/{_safe_name(filename)}"
    _ensure_bucket(db, s.storage_bucket)
    db.storage.from_(s.storage_bucket).upload(path, content, {"content-type": mime, "upsert": "true"})

    try:
        doc = (
            db.table("documents")
            .insert(
                {
                    "firm_id": firm_id,
                    "client_id": client_id,
                    "source": source,
                    "channel_ref": channel_ref,
                    "dedupe_key": key,
                    "kind": kind,
                    "original_name": filename,
                    "mime_type": mime,
                    "storage_path": path,
                    "size_bytes": len(content),
                    "sha256": key,
                    "status": "received",
                }
            )
            .execute()
            .data[0]
        )
    except APIError as e:
        if e.code == "23505":  # carrera: otro request insertó el mismo dedupe_key
            row = db.table("documents").select("id").eq("firm_id", firm_id).eq("dedupe_key", key).execute().data
            return IngestResult("duplicate", document_id=row[0]["id"] if row else None)
        raise

    doc_id = doc["id"]
    if kind == "bank_statement":
        # El parseo de extractos es Fase 3 (conciliación); se guarda y queda pendiente.
        return IngestResult("stored", document_id=doc_id, detail="Extracto guardado; se procesa en conciliación")
    if kind == "other":
        _update_doc(db, doc_id, status="ignored", error_detail=f"Tipo de archivo no soportado: {mime}")
        return IngestResult("error", document_id=doc_id, detail=f"Tipo de archivo no soportado: {mime}")

    _update_doc(db, doc_id, status="parsing")
    try:
        extracted = parse_ubl_invoice(content) if kind == "invoice_xml" else extract_invoice_vision(content, mime)
        invoice_id = _persist_invoice(db, client, doc_id, extracted)
    except _DuplicateInvoice as e:
        _update_doc(db, doc_id, status="ignored", error_detail=str(e), parsed=True)
        return IngestResult("duplicate", document_id=doc_id, detail=str(e))
    except ExtractionError as e:
        log.warning("extraction_failed", document_id=doc_id, error=str(e))
        _update_doc(db, doc_id, status="error", error_detail=str(e))
        return IngestResult("error", document_id=doc_id, detail=str(e))
    except Exception as e:  # nunca perder el original: queda en error con detalle
        log.exception("ingest_unexpected_error", document_id=doc_id)
        _update_doc(db, doc_id, status="error", error_detail=f"Error inesperado: {e}")
        return IngestResult("error", document_id=doc_id, detail=f"Error inesperado: {e}")

    _update_doc(db, doc_id, status="parsed", parsed=True)
    return IngestResult("parsed", document_id=doc_id, invoice_id=invoice_id, warnings=extracted.warnings)


class _DuplicateInvoice(Exception):
    pass


def _update_doc(db: Client, doc_id: str, *, status: str, error_detail: str | None = None, parsed: bool = False) -> None:
    patch: dict[str, Any] = {"status": status, "error_detail": error_detail}
    if parsed:
        patch["parsed_at"] = datetime.now(ZoneInfo("UTC")).isoformat()
    db.table("documents").update(patch).eq("id", doc_id).execute()


def resolve_direction(client_nit: str, inv: ExtractedInvoice) -> str:
    mine = normalize_nit(client_nit)
    if inv.supplier_nit == mine:
        return "emitida"
    if inv.customer_nit == mine:
        return "recibida"
    raise ExtractionError(
        f"La factura ({inv.supplier_nit} → {inv.customer_nit}) no involucra el NIT del cliente ({mine})"
    )


def _persist_invoice(db: Client, client: dict, doc_id: str, inv: ExtractedInvoice) -> str:
    direction = resolve_direction(client["nit"], inv)
    firm_id = client["firm_id"]

    dup = (
        db.table("invoices").select("id")
        .eq("firm_id", firm_id).eq("supplier_nit", inv.supplier_nit)
        .eq("invoice_number", inv.invoice_number).eq("direction", direction)
        .execute().data
    )
    if not dup and inv.cufe:
        dup = db.table("invoices").select("id").eq("firm_id", firm_id).eq("cufe", inv.cufe).execute().data
    if dup:
        raise _DuplicateInvoice(f"La factura {inv.invoice_number} ya existe (mismo emisor/número o CUFE)")

    notes = "; ".join(inv.warnings) or None
    row = {
        "firm_id": firm_id,
        "client_id": client["id"],
        "document_id": doc_id,
        "direction": direction,
        "supplier_nit": inv.supplier_nit,
        "supplier_name": inv.supplier_name,
        "customer_nit": inv.customer_nit,
        "customer_name": inv.customer_name,
        "invoice_number": inv.invoice_number,
        "cufe": inv.cufe,
        "issue_date": inv.issue_date.isoformat(),
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "currency": inv.currency,
        "fx_rate_to_cop": float(inv.fx_rate_to_cop) if inv.fx_rate_to_cop else None,
        "subtotal": float(inv.subtotal),
        "iva": float(inv.iva),
        "rete_fuente": float(inv.rete_fuente),
        "rete_iva": float(inv.rete_iva),
        "rete_ica": float(inv.rete_ica),
        "total": float(inv.total),
        "total_cop": float(inv.total_cop),
        "notes": notes,
    }
    invoice_id = db.table("invoices").insert(row).execute().data[0]["id"]
    if inv.lines:
        try:
            db.table("invoice_lines").insert(
                [
                    {
                        "invoice_id": invoice_id,
                        "line_no": i,
                        "description": ln.description,
                        "quantity": float(ln.quantity),
                        "unit_price": float(ln.unit_price),
                        "subtotal": float(ln.subtotal),
                        "iva_rate": float(ln.iva_rate),
                        "iva_amount": float(ln.iva_amount),
                        "total": float(ln.total),
                    }
                    for i, ln in enumerate(inv.lines, start=1)
                ]
            ).execute()
        except Exception:
            db.table("invoices").delete().eq("id", invoice_id).execute()
            raise
    return invoice_id
