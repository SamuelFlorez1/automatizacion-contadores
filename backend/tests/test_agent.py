"""Tests del agente WhatsApp: tools contra DB fake, loop con Anthropic mock.

No requiere Supabase real ni ANTHROPIC_API_KEY. Los tests construyen un
`FakeSupabase` que devuelve datos determinísticos y una fábrica que simula
respuestas del modelo Sonnet (bloques tool_use / text).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from app.agent import loop as loop_module
from app.agent.tools import (
    TOOL_SCHEMAS,
    execute_get_missing_documents,
    execute_get_pending_invoices,
    execute_get_tax_obligations,
    execute_search_document,
    execute_tool,
)
from app.notifications import reminders as reminders_module


# --------------------------------------------------------------- fake Supabase
class FakeQuery:
    def __init__(self, table: "FakeTable", *, is_delete=False, is_update=False, is_insert=False,
                 update_payload=None, insert_payload=None):
        self._table = table
        self._filters: list[tuple[str, str, Any]] = []
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None
        self._or: str | None = None
        self._in: tuple[str, list[Any]] | None = None
        self._is: tuple[str, Any] | None = None
        self._select_cols = "*"
        self._count_mode = None
        self._is_delete = is_delete
        self._is_update = is_update
        self._is_insert = is_insert
        self._update_payload = update_payload
        self._insert_payload = insert_payload

    def select(self, cols="*", count=None):
        self._select_cols = cols
        self._count_mode = count
        return self

    def eq(self, col, val): self._filters.append(("eq", col, val)); return self
    def gte(self, col, val): self._filters.append(("gte", col, val)); return self
    def lte(self, col, val): self._filters.append(("lte", col, val)); return self
    def ilike(self, col, val): self._filters.append(("ilike", col, val)); return self
    def in_(self, col, vals): self._in = (col, list(vals)); return self
    def is_(self, col, val): self._is = (col, val); return self
    def or_(self, expr): self._or = expr; return self
    def order(self, col, desc=False): self._order = (col, desc); return self
    def limit(self, n): self._limit = n; return self

    def _apply(self) -> list[dict]:
        rows = list(self._table.rows)
        for op, col, val in self._filters:
            if op == "eq":
                rows = [r for r in rows if r.get(col) == val]
            elif op == "gte":
                rows = [r for r in rows if (r.get(col) or "") >= val]
            elif op == "lte":
                rows = [r for r in rows if (r.get(col) or "") <= val]
            elif op == "ilike":
                needle = val.replace("%", "").lower()
                rows = [r for r in rows if needle in str(r.get(col, "")).lower()]
        if self._in:
            col, vals = self._in
            rows = [r for r in rows if r.get(col) in vals]
        if self._is:
            col, val = self._is
            if val == "null":
                rows = [r for r in rows if r.get(col) is None]
        if self._or:
            # crude: split by comma, treat each as `col.ilike.%needle%`
            keep: list[dict] = []
            clauses = [c.strip() for c in self._or.split(",")]
            for r in rows:
                for cl in clauses:
                    try:
                        col, op, val = cl.split(".", 2)
                    except ValueError:
                        continue
                    if op == "ilike":
                        needle = val.replace("%", "").lower()
                        if needle in str(r.get(col, "")).lower():
                            keep.append(r); break
            rows = keep
        if self._order:
            col, desc = self._order
            rows.sort(key=lambda r: (r.get(col) is None, r.get(col)), reverse=desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        return rows

    def execute(self):
        if self._is_insert:
            payload = self._insert_payload
            if isinstance(payload, dict):
                payload = [payload]
            for p in payload:
                p.setdefault("id", f"gen-{len(self._table.rows) + 1}")
                self._table.rows.append(dict(p))
            return SimpleNamespace(data=list(payload), count=len(payload))
        if self._is_update:
            rows = self._apply()
            for r in rows:
                r.update(self._update_payload or {})
            return SimpleNamespace(data=rows, count=len(rows))
        if self._is_delete:
            rows = self._apply()
            for r in rows:
                self._table.rows.remove(r)
            return SimpleNamespace(data=rows, count=len(rows))
        rows = self._apply()
        return SimpleNamespace(data=rows, count=len(rows))


class FakeTable:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def select(self, cols="*", count=None):
        q = FakeQuery(self)
        return q.select(cols, count=count)

    def insert(self, payload):
        return FakeQuery(self, is_insert=True, insert_payload=payload)

    def update(self, payload):
        return FakeQuery(self, is_update=True, update_payload=payload)

    def delete(self):
        return FakeQuery(self, is_delete=True)


class FakeSupabase:
    def __init__(self, tables: dict[str, list[dict]]):
        self._tables = {name: FakeTable(rows) for name, rows in tables.items()}

    def table(self, name: str) -> FakeTable:
        return self._tables.setdefault(name, FakeTable([]))


@pytest.fixture
def client_row():
    return {"id": "c1", "firm_id": "f1", "nit": "900111222",
            "phone": "+573001112233", "legal_name": "Consultora Andina SAS"}


@pytest.fixture
def fake_db(client_row):
    today = date.today()
    return FakeSupabase({
        "clients": [client_row],
        "documents": [
            {"id": "d1", "client_id": "c1", "firm_id": "f1", "original_name": "fac1.pdf",
             "status": "error", "error_detail": "PDF ilegible", "received_at": "2026-09-01T10:00:00Z", "kind": "invoice_pdf"},
            {"id": "d2", "client_id": "c1", "firm_id": "f1", "original_name": "fac2.xml",
             "status": "parsed", "received_at": "2026-09-02T10:00:00Z", "kind": "invoice_xml"},
        ],
        "invoices": [
            {"id": "i1", "client_id": "c1", "firm_id": "f1", "invoice_number": "FA-100",
             "supplier_name": "ETB SA", "supplier_nit": "899999115", "issue_date": "2026-07-15",
             "total_cop": 119000, "puc_account": "513535", "direction": "recibida"},
            {"id": "i2", "client_id": "c1", "firm_id": "f1", "invoice_number": "FA-101",
             "supplier_name": "Codensa", "supplier_nit": "830037248", "issue_date": "2026-08-05",
             "total_cop": 250000, "puc_account": None, "direction": "recibida"},
            {"id": "i3", "client_id": "c1", "firm_id": "f1", "invoice_number": "FV-1",
             "supplier_name": "Consultora Andina", "supplier_nit": "900111222", "issue_date": "2026-09-10",
             "total_cop": 5000000, "puc_account": "4155", "direction": "emitida"},
        ],
        "tax_obligations": [
            {"id": "o1", "client_id": "c1", "firm_id": "f1", "kind": "iva_bimestral",
             "period_label": "jul-ago-2026", "due_date": (today + timedelta(days=5)).isoformat(),
             "amount": 1200000, "status": "pending"},
            {"id": "o2", "client_id": "c1", "firm_id": "f1", "kind": "ica_bogota",
             "period_label": "jul-ago-2026", "due_date": (today + timedelta(days=2)).isoformat(),
             "amount": 340000, "status": "pending"},
            {"id": "o3", "client_id": "c1", "firm_id": "f1", "kind": "rete_fuente",
             "period_label": "2026-06", "due_date": (today - timedelta(days=10)).isoformat(),
             "amount": 500000, "status": "overdue"},
        ],
        "conversations": [],
        "messages": [],
    })


# --------------------------------------------------------------- tool schemas
def test_all_tool_schemas_valid():
    names = {t["name"] for t in TOOL_SCHEMAS}
    assert names == {"get_pending_invoices", "get_tax_obligations",
                     "get_missing_documents", "search_document", "escalate_to_human"}
    for t in TOOL_SCHEMAS:
        assert "input_schema" in t and t["input_schema"]["type"] == "object"


# --------------------------------------------------------------- tools puros
def test_get_tax_obligations_pending(fake_db, client_row):
    res = execute_get_tax_obligations(fake_db, client_row, {"status": "pending", "days_ahead": 30})
    assert res.ok
    # 2 pending (5d y 2d) están dentro del horizonte; overdue tiene due_date pasado y <= horizon → también entra
    assert len(res.data["obligations"]) >= 2
    assert "$" in res.summary
    assert "IVA bimestral" in res.summary


def test_get_pending_invoices(fake_db, client_row):
    res = execute_get_pending_invoices(fake_db, client_row, {})
    assert res.ok
    # 1 documento con status=error + 1 factura sin puc_account
    assert any(d["id"] == "d1" for d in res.data["documents"])
    assert any(i["id"] == "i2" for i in res.data["invoices"])
    assert "Codensa" in res.summary


def test_get_missing_documents_marks_months_without_invoices(fake_db, client_row):
    res = execute_get_missing_documents(fake_db, client_row, {"year": 2026})
    assert res.ok
    # Facturas de jul/ago/sep → falta ene..jun (según mes actual)
    missing = res.data["missing_months"]
    assert "ene" in missing
    assert "jul" not in missing  # jul tiene factura


def test_search_document_by_supplier(fake_db, client_row):
    res = execute_search_document(fake_db, client_row, {"query": "Codensa"})
    assert res.ok
    assert len(res.data["invoices"]) == 1
    assert res.data["invoices"][0]["invoice_number"] == "FA-101"


def test_execute_tool_escalate_marks_conversation(fake_db, client_row):
    # Precondición: crear conversación
    fake_db.table("conversations").insert({
        "id": "conv-1", "firm_id": "f1", "client_id": "c1", "channel": "whatsapp", "status": "active",
    }).execute()
    res = execute_tool("escalate_to_human", {"reason": "requerimiento DIAN"},
                       db=fake_db, client=client_row, conversation_id="conv-1")
    assert res.ok and res.data["escalated"]
    convs = fake_db.table("conversations").select().eq("id", "conv-1").execute().data
    assert convs[0]["status"] == "escalated"


def test_execute_tool_unknown(fake_db, client_row):
    res = execute_tool("no_existe", {}, db=fake_db, client=client_row, conversation_id="x")
    assert not res.ok


# --------------------------------------------------------------- loop mock
def _mk_tool_use_block(name, args, tid="tu_1"):
    return SimpleNamespace(
        type="tool_use", name=name, input=args, id=tid,
        model_dump=lambda: {"type": "tool_use", "name": name, "input": args, "id": tid},
    )


def _mk_text_block(text):
    return SimpleNamespace(
        type="text", text=text,
        model_dump=lambda: {"type": "text", "text": text},
    )


def _mk_response(*blocks, stop="end_turn"):
    return SimpleNamespace(
        content=list(blocks), stop_reason=stop,
        usage=SimpleNamespace(input_tokens=100, output_tokens=50),
    )


@dataclass
class FakeAnthropic:
    scripted: list  # lista de respuestas a devolver en orden

    def __post_init__(self):
        self.messages = SimpleNamespace(create=self._create)
        self._i = 0

    def _create(self, **kwargs):
        r = self.scripted[self._i]
        self._i += 1
        return r


def test_loop_uses_tool_then_replies(fake_db, client_row, monkeypatch):
    scripted = [
        _mk_response(_mk_tool_use_block("get_tax_obligations", {"days_ahead": 15}), stop="tool_use"),
        _mk_response(_mk_text_block("Tienes IVA por $1.200.000 que vence en 5 días.")),
    ]
    monkeypatch.setattr(loop_module, "_client", lambda: FakeAnthropic(scripted))

    # Conv previa
    fake_db.table("conversations").insert({
        "id": "conv-1", "firm_id": "f1", "client_id": "c1", "channel": "whatsapp", "status": "active",
    }).execute()

    reply = loop_module.run_agent(
        db=fake_db, client=client_row, conversation_id="conv-1",
        user_message="¿cuánto debo de impuestos?", prior_turns=[],
    )
    assert not reply.escalated
    assert reply.iterations == 2
    assert reply.tools_called == ["get_tax_obligations"]
    assert "1.200.000" in reply.text
    # se persistió el mensaje final + el tool_result
    roles = [m["role"] for m in fake_db.table("messages").select().execute().data]
    assert "tool" in roles and "assistant" in roles


def test_loop_without_api_key_returns_escalation(fake_db, client_row, monkeypatch):
    monkeypatch.setattr(loop_module, "_client", lambda: None)
    fake_db.table("conversations").insert({
        "id": "conv-2", "firm_id": "f1", "client_id": "c1", "channel": "whatsapp", "status": "active",
    }).execute()
    reply = loop_module.run_agent(
        db=fake_db, client=client_row, conversation_id="conv-2",
        user_message="hola", prior_turns=[],
    )
    assert reply.escalated
    assert "contador" in reply.text.lower()


def test_loop_hard_stops_on_max_iterations(fake_db, client_row, monkeypatch):
    # Modelo que solo pide tools infinitamente
    scripted = [
        _mk_response(_mk_tool_use_block("get_pending_invoices", {}, tid=f"tu_{i}"), stop="tool_use")
        for i in range(loop_module.MAX_ITERS + 2)
    ]
    monkeypatch.setattr(loop_module, "_client", lambda: FakeAnthropic(scripted))
    fake_db.table("conversations").insert({
        "id": "conv-3", "firm_id": "f1", "client_id": "c1", "channel": "whatsapp", "status": "active",
    }).execute()
    reply = loop_module.run_agent(
        db=fake_db, client=client_row, conversation_id="conv-3",
        user_message="bucle", prior_turns=[],
    )
    assert reply.escalated
    assert reply.iterations == loop_module.MAX_ITERS


# --------------------------------------------------------------- reminders
def test_reminders_groups_and_sends(fake_db, monkeypatch):
    sent = []
    monkeypatch.setattr(reminders_module, "get_service_client", lambda: fake_db)
    monkeypatch.setattr(reminders_module, "send_text",
                        lambda phone, text: sent.append((phone, text)) or {"ok": True, "to": phone})
    res = reminders_module.run_reminders(today=date.today())
    assert res["sent"] == 1  # solo un cliente con obligaciones en 5/2/0 días
    assert len(sent) == 1
    phone, text = sent[0]
    assert "IVA bimestral" in text or "ICA Bogotá" in text


def test_reminders_skips_client_without_phone(fake_db, monkeypatch, client_row):
    client_row["phone"] = None
    monkeypatch.setattr(reminders_module, "get_service_client", lambda: fake_db)
    monkeypatch.setattr(reminders_module, "send_text",
                        lambda phone, text: {"ok": True})
    res = reminders_module.run_reminders(today=date.today())
    assert res["sent"] == 0 and res["skipped"] == 1
