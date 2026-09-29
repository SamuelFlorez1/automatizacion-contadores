"""Parser de extractos bancarios CSV.

Formato esperado (compatible con seed):

    # Cuenta,Bancolombia ****3421,Moneda,COP
    fecha,descripcion,referencia,valor,saldo
    2026-07-01,SALDO INICIAL,,8000000.00,8000000.00
    2026-07-10,PAGO A ETB,FCA-R-202607-003,-160000.00,7660000.00

Tolerante a:
- Comentarios `#` al inicio (metadatos).
- Separador `,` o `;`.
- Codificación UTF-8 o latin-1.
- Encabezados en español (fecha/descripcion/valor/saldo) o inglés (date/description/amount/balance).
- Formato de valores `1.234.567,89` (europeo) o `1234567.89`.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256


class CsvParseError(ValueError):
    pass


@dataclass
class BankAccountHint:
    bank_name: str = ""
    account_number_masked: str = ""
    currency: str = "COP"
    account_type: str = "corriente"


@dataclass
class ParsedTxn:
    tx_date: date
    description: str
    reference: str | None
    amount: Decimal
    currency: str
    balance_after: Decimal | None
    dedupe_key: str


@dataclass
class ParsedStatement:
    account: BankAccountHint
    txns: list[ParsedTxn] = field(default_factory=list)


# --------------------------------------------------------------- helpers
_HEADER_ALIASES = {
    "fecha": "date", "date": "date",
    "descripcion": "description", "descripción": "description", "concepto": "description",
    "detalle": "description", "description": "description",
    "referencia": "reference", "ref": "reference", "reference": "reference",
    "documento": "reference",
    "valor": "amount", "monto": "amount", "importe": "amount", "amount": "amount",
    "saldo": "balance", "balance": "balance",
}


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise CsvParseError("No se pudo decodificar el archivo")


def _sniff_dialect(sample: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;|\t")
    except csv.Error:
        return csv.excel  # coma por defecto


def _parse_amount(raw: str) -> Decimal:
    s = raw.strip().replace(" ", "")
    if not s:
        return Decimal("0")
    # Formato "1.234.567,89" → "1234567.89"
    if "," in s and s.count(",") == 1 and re.search(r"\.\d{3}", s):
        s = s.replace(".", "").replace(",", ".")
    # Formato "1.234,56"
    elif "," in s and s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    # Signos entre paréntesis (contabilidad): (123.45) → -123.45
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return Decimal(s)
    except InvalidOperation as e:
        raise CsvParseError(f"Valor no numérico: {raw!r}") from e


def _parse_date(raw: str) -> date:
    s = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise CsvParseError(f"Fecha no reconocida: {raw!r}")


def _parse_meta_line(line: str) -> dict[str, str]:
    """`# Cuenta,Bancolombia ****3421,Moneda,COP` → dict."""
    body = line.lstrip("#").strip()
    parts = [p.strip() for p in re.split(r"[,;|]", body)]
    out: dict[str, str] = {}
    it = iter(parts)
    for k in it:
        try:
            v = next(it)
        except StopIteration:
            break
        out[k.lower()] = v
    return out


_MASK_RE = re.compile(r"(\*{2,}[A-Z0-9]+|\b\d{4,})")


def _derive_account(meta: dict[str, str]) -> BankAccountHint:
    hint = BankAccountHint()
    cuenta = meta.get("cuenta") or meta.get("account") or ""
    if cuenta:
        m = _MASK_RE.search(cuenta)
        if m:
            hint.account_number_masked = m.group(0)
            bank = cuenta[: m.start()].strip(" -,").strip()
        else:
            bank = cuenta.strip()
        hint.bank_name = bank or "Banco"
    for k in ("moneda", "currency"):
        if v := meta.get(k):
            hint.currency = v.upper()[:3]
    for k in ("tipo", "account_type"):
        if v := meta.get(k):
            hint.account_type = v.lower()
    if not hint.account_number_masked:
        hint.account_number_masked = "****"
    return hint


# --------------------------------------------------------------- parser
def parse_bank_csv(content: bytes, *, account_hint: BankAccountHint | None = None) -> ParsedStatement:
    text = _decode(content)
    lines = text.splitlines()

    meta: dict[str, str] = {}
    data_lines: list[str] = []
    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            meta.update(_parse_meta_line(stripped))
            continue
        data_lines.append(ln)

    if not data_lines:
        raise CsvParseError("CSV vacío")

    dialect = _sniff_dialect("\n".join(data_lines[:5]))
    reader = csv.reader(data_lines, dialect=dialect)
    rows = list(reader)
    if len(rows) < 2:
        raise CsvParseError("CSV sin datos")

    header_raw = [c.strip().lower() for c in rows[0]]
    header = [_HEADER_ALIASES.get(c, c) for c in header_raw]
    required = {"date", "description", "amount"}
    if not required.issubset(header):
        raise CsvParseError(f"Faltan columnas requeridas ({required}); llegaron {header_raw}")

    idx = {name: header.index(name) for name in header if name in _HEADER_ALIASES.values()}
    account = account_hint or _derive_account(meta)

    txns: list[ParsedTxn] = []
    for i, row in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in row):
            continue
        try:
            desc = row[idx["description"]].strip()
            # Saldos iniciales / de corte se ignoran para conciliación.
            if re.fullmatch(r"saldo\s+(inicial|anterior|final)\s*", desc, re.I):
                continue
            amount = _parse_amount(row[idx["amount"]])
            tx = ParsedTxn(
                tx_date=_parse_date(row[idx["date"]]),
                description=desc,
                reference=(row[idx["reference"]].strip() if "reference" in idx and len(row) > idx["reference"] else None) or None,
                amount=amount,
                currency=account.currency,
                balance_after=_parse_amount(row[idx["balance"]]) if "balance" in idx and len(row) > idx["balance"] and row[idx["balance"]].strip() else None,
                dedupe_key="",  # se calcula abajo
            )
        except CsvParseError as e:
            raise CsvParseError(f"Fila {i}: {e}") from e
        payload = f"{account.account_number_masked}|{tx.tx_date}|{tx.amount}|{tx.reference or ''}|{tx.description}"
        tx.dedupe_key = sha256(payload.encode("utf-8")).hexdigest()
        txns.append(tx)

    if not txns:
        raise CsvParseError("CSV sin movimientos")
    return ParsedStatement(account=account, txns=txns)
