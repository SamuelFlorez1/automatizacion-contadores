"""Seed principal — puebla Supabase con datos de demo.

Uso:
    cd backend
    source .venv/bin/activate
    python -m seeds.seed
"""

from __future__ import annotations

import hashlib
import os
import random
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import psycopg
from psycopg.types.json import Json

from seeds.generators import (
    BankTx,
    Invoice,
    InvoiceLine,
    Party,
    build_ubl_xml,
    nit_dv,
    render_invoice_png,
    synthetic_cufe,
    write_bank_csv,
)

random.seed(20260928)

SEEDS_DIR = Path(__file__).parent
XML_DIR = SEEDS_DIR / "invoices_xml"
IMG_DIR = SEEDS_DIR / "invoices_images"
BANK_DIR = SEEDS_DIR / "bank_statements"


def _load_db_url() -> str:
    env = Path(__file__).resolve().parents[2] / ".env"
    for line in env.read_text().splitlines():
        if line.startswith("SUPABASE_DB_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("SUPABASE_DB_URL no encontrada en .env")


# -----------------------------------------------------------------------------
# Datos maestros
# -----------------------------------------------------------------------------
FIRM_NIT = "900456789"
FIRM_DV = nit_dv(FIRM_NIT)
FIRM_NAME = "Despacho Contable Demo SAS"

CLIENT_A = {
    "nit": "901234567",
    "legal_name": "Consultora Andina SAS",
    "tax_regime": "simple",
    "iva_frequency": "no_aplica",
    "ica_activity_code": "749",
    "is_agente_retencion": False,
    "default_currency": "COP",
    "phone": "+573001112233",
    "email": "contacto@consultoraandina.co",
    "address": "Cra 11 # 93-45 Of 502",
}
CLIENT_B = {
    "nit": "830987654",
    "legal_name": "Comercializadora Pacífico SAS",
    "tax_regime": "ordinario",
    "iva_frequency": "bimestral",
    "ica_activity_code": "466",
    "is_agente_retencion": True,
    "default_currency": "COP",
    "phone": "+573014445566",
    "email": "contabilidad@compacifico.co",
    "address": "Cl 26 # 68-35 Bod 12",
}

# Contrapartes recurrentes
SUPPLIERS_A_RECIBIDAS = [
    ("Arrendamientos Bogotá SA",     "860500123", "Cl 100 # 15-40",           "Arriendo oficina",                     600_000, 0.00),
    ("Codensa SA ESP",               "830037248", "Cr 13a # 93-66",           "Servicio de energía eléctrica",         180_000, 0.00),
    ("ETB",                          "899999115", "Cl 23 # 13-49",            "Servicio de internet y telefonía",      160_000, 0.00),
    ("Papelería Central",            "800150250", "Cl 12 # 5-10",             "Útiles y papelería",                     95_000, 0.19),
    ("Estudio Legal & Asociados",    "900112233", "Cr 7 # 71-52 Of 801",      "Honorarios asesoría jurídica",         900_000, 0.00),
]
CUSTOMERS_A_EMITIDAS = [
    ("Inversiones El Roble SAS",     "900333555", "Cl 72 # 10-34"),
    ("Grupo Educativo Norte",        "800556677", "Av Suba 100-20"),
    ("Fundación Progresar",          "901776655", "Cr 15 # 45-12"),
]

SUPPLIERS_B_RECIBIDAS = [
    ("Distribuidora El Sol SAS",     "900112211", "Cl 13 # 68-90 Bod 5",      "Compra mercancía surtido",           1_800_000, 0.19),
    ("Proveedora Nacional Ltda",     "830224466", "Cl 80 # 68-45",            "Compra mercancía electrónica",       3_200_000, 0.19),
    ("Transportes Rápidos SAS",      "900556677", "Cl 26 # 92-15",            "Servicio de transporte de carga",       450_000, 0.19),
    ("Bodegas Centro Ltda",          "860700800", "Cl 15 # 30-22",            "Arriendo bodega",                    2_200_000, 0.00),
    ("Servicios Contables Uno",      "901223344", "Cr 11 # 78-25",            "Honorarios contables mensuales",     1_500_000, 0.00),
]
SUPPLIERS_B_USD = [
    ("Shenzhen Electronics Co",      "999000111", "Shenzhen, China",          "Import — auriculares Bluetooth",     6_500.00, 0.00),
    ("Miami Wholesale LLC",          "999000222", "Miami FL, USA",            "Import — accesorios para celular",   4_200.00, 0.00),
]
CUSTOMERS_B_EMITIDAS = [
    ("Almacenes Vista SAS",          "830445566", "Cl 53 # 25-18"),
    ("Cadena Puntual SAS",           "900889977", "Av 68 # 40-20"),
    ("Distribuciones Sur Ltda",      "830660011", "Cl 22 sur # 30-10"),
]


def party_from_tuple(t: tuple[str, str, str]) -> Party:
    name, nit, address = t
    return Party(nit=nit, dv=nit_dv(nit), name=name, address=address)


def party_of_client(c: dict) -> Party:
    return Party(nit=c["nit"], dv=nit_dv(c["nit"]), name=c["legal_name"], address=c["address"])


# -----------------------------------------------------------------------------
# Generación de facturas
# -----------------------------------------------------------------------------
def make_recibida_cop(number: str, issue: date, supplier_t, client_c: dict, rete_f: float = 0.0) -> Invoice:
    name, nit, addr, concept, unit_price, iva_rate = supplier_t
    lines = [InvoiceLine(description=concept, quantity=1, unit_price=unit_price, iva_rate=iva_rate)]
    inv = Invoice(
        number=number,
        cufe="",
        issue_date=issue,
        due_date=issue + timedelta(days=30),
        supplier=Party(nit=nit, dv=nit_dv(nit), name=name, address=addr),
        customer=party_of_client(client_c),
        lines=lines,
        rete_fuente_rate=rete_f,
    )
    inv.cufe = synthetic_cufe(number, issue, nit, inv.total)
    return inv


def make_emitida_servicios(number: str, issue: date, customer_t, client_c: dict) -> Invoice:
    name, nit, addr = customer_t
    hours = random.choice([20, 30, 40, 60])
    rate = random.choice([80_000, 120_000, 150_000])
    lines = [InvoiceLine(description=f"Consultoría estratégica — {hours}h", quantity=hours, unit_price=rate, iva_rate=0.19)]
    inv = Invoice(
        number=number,
        cufe="",
        issue_date=issue,
        due_date=issue + timedelta(days=30),
        supplier=party_of_client(client_c),
        customer=Party(nit=nit, dv=nit_dv(nit), name=name, address=addr),
        lines=lines,
    )
    inv.cufe = synthetic_cufe(number, issue, client_c["nit"], inv.total)
    return inv


def make_emitida_comercio(number: str, issue: date, customer_t, client_c: dict) -> Invoice:
    name, nit, addr = customer_t
    n_items = random.randint(1, 3)
    lines = []
    for _ in range(n_items):
        qty = random.randint(10, 100)
        price = random.randint(20_000, 120_000)
        product = random.choice([
            "Auriculares Bluetooth ref A100", "Cargador USB-C 20W", "Cable HDMI 2m",
            "Base para laptop", "Mouse inalámbrico", "Teclado mecánico",
        ])
        lines.append(InvoiceLine(description=product, quantity=qty, unit_price=price, iva_rate=0.19))
    inv = Invoice(
        number=number,
        cufe="",
        issue_date=issue,
        due_date=issue + timedelta(days=45),
        supplier=party_of_client(client_c),
        customer=Party(nit=nit, dv=nit_dv(nit), name=name, address=addr),
        lines=lines,
    )
    inv.cufe = synthetic_cufe(number, issue, client_c["nit"], inv.total)
    return inv


def make_recibida_usd(number: str, issue: date, supplier_t, client_c: dict, fx: float) -> Invoice:
    name, nit, addr, concept, usd_price, _ = supplier_t
    lines = [InvoiceLine(description=concept, quantity=1, unit_price=usd_price, iva_rate=0.0)]
    inv = Invoice(
        number=number,
        cufe="",
        issue_date=issue,
        due_date=issue + timedelta(days=60),
        supplier=Party(nit=nit, dv=nit_dv(nit), name=name, address=addr),
        customer=party_of_client(client_c),
        currency="USD",
        fx_rate_to_cop=fx,
        lines=lines,
    )
    inv.cufe = synthetic_cufe(number, issue, nit, inv.total)
    return inv


# -----------------------------------------------------------------------------
# Inserción en Supabase
# -----------------------------------------------------------------------------
def wipe(cur) -> None:
    for t in [
        "reconciliation_matches", "bank_transactions", "bank_accounts",
        "invoice_lines", "invoices", "documents",
        "tax_obligations", "messages", "conversations",
        "audit_log", "clients", "users", "firms",
    ]:
        cur.execute(f"delete from {t}")


def insert_firm(cur) -> str:
    fid = str(uuid.uuid4())
    cur.execute(
        "insert into firms (id, name, nit, city) values (%s, %s, %s, %s)",
        (fid, FIRM_NAME, f"{FIRM_NIT}-{FIRM_DV}", "Bogotá"),
    )
    return fid


def insert_client(cur, firm_id: str, c: dict) -> str:
    cid = str(uuid.uuid4())
    cur.execute(
        """insert into clients (id, firm_id, legal_name, nit, nit_dv, tax_regime, iva_frequency,
               ica_city, ica_activity_code, is_agente_retencion, default_currency,
               phone, email, address)
           values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (cid, firm_id, c["legal_name"], c["nit"], nit_dv(c["nit"]),
         c["tax_regime"], c["iva_frequency"], "Bogotá", c["ica_activity_code"],
         c["is_agente_retencion"], c["default_currency"],
         c["phone"], c["email"], c["address"]),
    )
    return cid


def insert_bank_account(cur, firm_id: str, client_id: str, bank: str, acc_type: str, masked: str, currency: str) -> str:
    aid = str(uuid.uuid4())
    cur.execute(
        """insert into bank_accounts (id, firm_id, client_id, bank_name, account_type, account_number_masked, currency)
           values (%s,%s,%s,%s,%s,%s,%s)""",
        (aid, firm_id, client_id, bank, acc_type, masked, currency),
    )
    return aid


def insert_invoice(cur, firm_id: str, client_id: str, inv: Invoice, direction: str, xml_bytes: bytes,
                    image_path: Path | None) -> str:
    # 1) documento
    doc_id = str(uuid.uuid4())
    dedupe = hashlib.sha256(xml_bytes).hexdigest()
    xml_path = XML_DIR / f"{inv.number}.xml"
    cur.execute(
        """insert into documents (id, firm_id, client_id, source, dedupe_key, kind,
               original_name, mime_type, storage_path, size_bytes, sha256, status, parsed_at)
           values (%s,%s,%s,'seed',%s,'invoice_xml',%s,'application/xml',%s,%s,%s,'parsed', now())""",
        (doc_id, firm_id, client_id, dedupe, xml_path.name, str(xml_path.relative_to(SEEDS_DIR.parent)),
         len(xml_bytes), dedupe),
    )
    xml_path.write_bytes(xml_bytes)

    if image_path is not None:
        img_id = str(uuid.uuid4())
        img_bytes = image_path.read_bytes()
        img_dedupe = hashlib.sha256(img_bytes + inv.number.encode()).hexdigest()
        cur.execute(
            """insert into documents (id, firm_id, client_id, source, dedupe_key, kind,
                   original_name, mime_type, storage_path, size_bytes, sha256, status)
               values (%s,%s,%s,'seed',%s,'invoice_image',%s,'image/png',%s,%s,%s,'received')""",
            (img_id, firm_id, client_id, img_dedupe, image_path.name,
             str(image_path.relative_to(SEEDS_DIR.parent)), len(img_bytes), img_dedupe),
        )

    # 2) invoice
    inv_id = str(uuid.uuid4())
    cur.execute(
        """insert into invoices (id, firm_id, client_id, document_id, direction,
               supplier_nit, supplier_name, customer_nit, customer_name,
               invoice_number, cufe, issue_date, due_date, currency, fx_rate_to_cop,
               subtotal, iva, rete_fuente, rete_ica, total, total_cop, payment_status)
           values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (inv_id, firm_id, client_id, doc_id, direction,
         inv.supplier.nit, inv.supplier.name, inv.customer.nit, inv.customer.name,
         inv.number, inv.cufe, inv.issue_date, inv.due_date, inv.currency, inv.fx_rate_to_cop,
         inv.subtotal, inv.iva, inv.rete_fuente, inv.rete_ica, inv.total, inv.total_cop,
         inv.payment_status),
    )
    for i, ln in enumerate(inv.lines, start=1):
        cur.execute(
            """insert into invoice_lines (invoice_id, line_no, description, quantity, unit_price,
                   subtotal, iva_rate, iva_amount, total)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (inv_id, i, ln.description, ln.quantity, ln.unit_price, ln.subtotal,
             ln.iva_rate * 100, ln.iva_amount, ln.total),
        )
    return inv_id


def insert_bank_tx(cur, firm_id: str, client_id: str, bank_account_id: str, tx: BankTx, currency: str) -> None:
    dedupe = hashlib.sha256(f"{bank_account_id}|{tx.tx_date}|{tx.description}|{tx.amount}".encode()).hexdigest()
    cur.execute(
        """insert into bank_transactions (firm_id, client_id, bank_account_id, tx_date, description,
               reference, amount, currency, balance_after, dedupe_key)
           values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           on conflict (firm_id, dedupe_key) do nothing""",
        (firm_id, client_id, bank_account_id, tx.tx_date, tx.description, tx.reference,
         tx.amount, currency, tx.balance_after, dedupe),
    )


# -----------------------------------------------------------------------------
# Orquestador
# -----------------------------------------------------------------------------
def build_all_invoices_client_a(client_id_num: str) -> list[tuple[Invoice, str]]:
    """Genera facturas Cliente A (Simple, servicios). Retorna (inv, direction)."""
    out: list[tuple[Invoice, str]] = []
    months = [(2026, 7), (2026, 8), (2026, 9)]
    seq_r, seq_e = 1, 1
    for y, m in months:
        # recibidas: 4-5 por mes (arriendo + servicios + variables)
        for supplier in SUPPLIERS_A_RECIBIDAS:
            day = random.randint(3, 26)
            issue = date(y, m, day)
            number = f"FCA-R-{y}{m:02d}-{seq_r:03d}"
            seq_r += 1
            inv = make_recibida_cop(number, issue, supplier, CLIENT_A, rete_f=0.04 if "Honorarios" in supplier[3] else 0.0)
            inv.payment_status = "paid" if random.random() < 0.7 else "pending"
            out.append((inv, "recibida"))
        # emitidas: 2-3 por mes
        for _ in range(random.randint(2, 3)):
            customer = random.choice(CUSTOMERS_A_EMITIDAS)
            day = random.randint(5, 27)
            issue = date(y, m, day)
            number = f"FCA-E-{y}{m:02d}-{seq_e:03d}"
            seq_e += 1
            inv = make_emitida_servicios(number, issue, customer, CLIENT_A)
            inv.payment_status = "paid" if random.random() < 0.6 else "pending"
            out.append((inv, "emitida"))
    return out


def build_all_invoices_client_b() -> list[tuple[Invoice, str]]:
    out: list[tuple[Invoice, str]] = []
    months = [(2026, 7), (2026, 8), (2026, 9)]
    fx_by_month = {7: 4050.0, 8: 4110.0, 9: 4080.0}
    seq_r, seq_e, seq_u = 1, 1, 1
    for y, m in months:
        # recibidas nacionales
        for supplier in SUPPLIERS_B_RECIBIDAS:
            day = random.randint(3, 27)
            issue = date(y, m, day)
            number = f"FCB-R-{y}{m:02d}-{seq_r:03d}"
            seq_r += 1
            rf = 0.025 if "Honorarios" in supplier[3] else (0.01 if supplier[5] > 0 else 0.0)
            inv = make_recibida_cop(number, issue, supplier, CLIENT_B, rete_f=rf)
            inv.payment_status = "paid" if random.random() < 0.75 else "pending"
            out.append((inv, "recibida"))
        # importaciones USD (1 por mes rotando)
        supplier = SUPPLIERS_B_USD[seq_u % len(SUPPLIERS_B_USD)]
        seq_u += 1
        day = random.randint(8, 20)
        issue = date(y, m, day)
        number = f"FCB-I-{y}{m:02d}-{seq_u:03d}"
        inv = make_recibida_usd(number, issue, supplier, CLIENT_B, fx=fx_by_month[m])
        inv.payment_status = "paid" if random.random() < 0.5 else "pending"
        out.append((inv, "recibida"))
        # emitidas nacionales
        for _ in range(random.randint(3, 5)):
            customer = random.choice(CUSTOMERS_B_EMITIDAS)
            day = random.randint(4, 28)
            issue = date(y, m, day)
            number = f"FCB-E-{y}{m:02d}-{seq_e:03d}"
            seq_e += 1
            inv = make_emitida_comercio(number, issue, customer, CLIENT_B)
            inv.payment_status = "paid" if random.random() < 0.55 else "pending"
            out.append((inv, "emitida"))
    return out


def build_bank_txs(invoices: list[tuple[Invoice, str]], opening_balance: float, currency: str, only_currency: str | None = None) -> list[BankTx]:
    txs: list[BankTx] = []
    balance = opening_balance
    # apertura
    txs.append(BankTx(tx_date=date(2026, 7, 1), description="SALDO INICIAL", reference="",
                      amount=opening_balance, balance_after=opening_balance))
    for inv, direction in sorted(invoices, key=lambda x: x[0].issue_date):
        if only_currency and inv.currency != only_currency:
            continue
        if inv.payment_status != "paid":
            continue
        pay_date = inv.issue_date + timedelta(days=random.randint(3, 25))
        amount = inv.total if inv.currency == currency else inv.total  # match monedas
        sign = 1 if direction == "emitida" else -1
        desc = ("ABONO CLIENTE " if direction == "emitida" else "PAGO A ") + (
            inv.customer.name if direction == "emitida" else inv.supplier.name
        )
        ref = inv.number
        balance += sign * amount
        txs.append(BankTx(tx_date=pay_date, description=desc[:60], reference=ref,
                          amount=sign * amount, balance_after=round(balance, 2)))
    # unos cuantos movimientos "huerfanos" para que la conciliación tenga trabajo real
    for _ in range(5):
        d = date(2026, random.choice([7, 8, 9]), random.randint(2, 27))
        val = -random.choice([25_000, 55_000, 82_000, 130_000])
        balance += val
        txs.append(BankTx(tx_date=d, description="RETIRO ATM CB07",
                          reference=f"ATM{random.randint(1000,9999)}",
                          amount=val, balance_after=round(balance, 2)))
    return sorted(txs, key=lambda t: t.tx_date)


def main() -> None:
    XML_DIR.mkdir(parents=True, exist_ok=True)
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    BANK_DIR.mkdir(parents=True, exist_ok=True)

    url = _load_db_url()
    with psycopg.connect(url, sslmode="require") as conn:
        with conn.cursor() as cur:
            print("→ Limpiando tablas…")
            wipe(cur)

            print("→ Insertando firm y clientes…")
            firm_id = insert_firm(cur)
            client_a_id = insert_client(cur, firm_id, CLIENT_A)
            client_b_id = insert_client(cur, firm_id, CLIENT_B)

            print("→ Cuentas bancarias…")
            acc_a = insert_bank_account(cur, firm_id, client_a_id,
                "Bancolombia", "ahorros", "****3421", "COP")
            acc_b_cop = insert_bank_account(cur, firm_id, client_b_id,
                "Davivienda", "corriente", "****8890", "COP")
            acc_b_usd = insert_bank_account(cur, firm_id, client_b_id,
                "Bancolombia", "ahorros", "****USD01", "USD")

            print("→ Facturas Cliente A (Simple)…")
            invs_a = build_all_invoices_client_a(CLIENT_A["nit"])
            for i, (inv, direction) in enumerate(invs_a):
                xml = build_ubl_xml(inv)
                img_path = None
                if i % 7 == 0:
                    img_path = IMG_DIR / f"{inv.number}.png"
                    render_invoice_png(inv, img_path)
                insert_invoice(cur, firm_id, client_a_id, inv, direction, xml, img_path)

            print("→ Facturas Cliente B (Ordinario + USD)…")
            invs_b = build_all_invoices_client_b()
            for i, (inv, direction) in enumerate(invs_b):
                xml = build_ubl_xml(inv)
                img_path = None
                if i % 8 == 0:
                    img_path = IMG_DIR / f"{inv.number}.png"
                    render_invoice_png(inv, img_path)
                insert_invoice(cur, firm_id, client_b_id, inv, direction, xml, img_path)

            print("→ Movimientos bancarios…")
            txs_a = build_bank_txs(invs_a, opening_balance=8_000_000, currency="COP")
            for t in txs_a:
                insert_bank_tx(cur, firm_id, client_a_id, acc_a, t, "COP")
            write_bank_csv(BANK_DIR / "consultora_andina_bancolombia_2026Q3.csv",
                           "Bancolombia ****3421", "COP", txs_a)

            txs_b_cop = build_bank_txs(invs_b, opening_balance=25_000_000, currency="COP", only_currency="COP")
            for t in txs_b_cop:
                insert_bank_tx(cur, firm_id, client_b_id, acc_b_cop, t, "COP")
            write_bank_csv(BANK_DIR / "compacifico_davivienda_2026Q3.csv",
                           "Davivienda ****8890", "COP", txs_b_cop)

            txs_b_usd = build_bank_txs(invs_b, opening_balance=15_000.00, currency="USD", only_currency="USD")
            for t in txs_b_usd:
                insert_bank_tx(cur, firm_id, client_b_id, acc_b_usd, t, "USD")
            write_bank_csv(BANK_DIR / "compacifico_bancolombia_usd_2026Q3.csv",
                           "Bancolombia ****USD01", "USD", txs_b_usd)

        conn.commit()

        with conn.cursor() as cur:
            for t in ["firms", "clients", "invoices", "invoice_lines",
                      "bank_accounts", "bank_transactions", "documents"]:
                cur.execute(f"select count(*) from {t}")
                print(f"  {t}: {cur.fetchone()[0]}")

    print("\n✅ Seed listo.")


if __name__ == "__main__":
    main()
