"""Crea usuarios demo en Supabase Auth y los enlaza a firms/clients.

Uso:
    cd backend && source .venv/bin/activate
    python -m seeds.seed_users
"""

from __future__ import annotations

from pathlib import Path

import psycopg
from supabase import create_client

USERS = [
    {"email": "admin@despachodemo.co",    "password": "DemoAdmin2026!", "role": "firm_admin", "full_name": "Admin Despacho",  "client_slug": None},
    {"email": "contador@despachodemo.co", "password": "DemoConta2026!", "role": "accountant", "full_name": "Contador Demo",   "client_slug": None},
    {"email": "andina@clientedemo.co",    "password": "DemoAndi2026!",  "role": "client",     "full_name": "Consultora Andina", "client_slug": "consultora"},
    {"email": "pacifico@clientedemo.co",  "password": "DemoPaci2026!",  "role": "client",     "full_name": "Comercializadora Pacífico", "client_slug": "pacifico"},
]


def _read_env(key: str) -> str:
    env = Path(__file__).resolve().parents[2] / ".env"
    for line in env.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"{key} no encontrada en .env")


def main() -> None:
    db_url = _read_env("SUPABASE_DB_URL")
    sb_url = _read_env("SUPABASE_URL")
    sb_service = _read_env("SUPABASE_SERVICE_ROLE_KEY")

    sb = create_client(sb_url, sb_service)

    with psycopg.connect(db_url, sslmode="require") as conn:
        with conn.cursor() as cur:
            cur.execute("select id from firms limit 1")
            row = cur.fetchone()
            if not row:
                raise RuntimeError("No hay firms. Corre `python -m seeds.seed` antes.")
            firm_id = row[0]

            cur.execute("select id, legal_name from clients")
            clients = {r[1].lower(): r[0] for r in cur.fetchall()}
            client_ids = {
                "consultora": next((v for k, v in clients.items() if "consultora" in k), None),
                "pacifico": next((v for k, v in clients.items() if "pac" in k), None),
            }

            for u in USERS:
                try:
                    created = sb.auth.admin.create_user({
                        "email": u["email"],
                        "password": u["password"],
                        "email_confirm": True,
                        "user_metadata": {"full_name": u["full_name"]},
                    })
                    uid = created.user.id
                    print(f"  auth.users creado: {u['email']} → {uid}")
                except Exception as e:
                    msg = str(e).lower()
                    if "already" in msg or "registered" in msg or "duplicate" in msg:
                        listed = sb.auth.admin.list_users()
                        uid = next((x.id for x in listed if x.email == u["email"]), None)
                        if not uid:
                            raise
                        print(f"  auth.users existente: {u['email']} → {uid}")
                    else:
                        raise

                client_id = client_ids.get(u["client_slug"]) if u["client_slug"] else None
                cur.execute(
                    """insert into users (id, firm_id, email, full_name, role, client_id)
                       values (%s,%s,%s,%s,%s,%s)
                       on conflict (id) do update set role = excluded.role,
                                                     full_name = excluded.full_name,
                                                     client_id = excluded.client_id""",
                    (uid, firm_id, u["email"], u["full_name"], u["role"], client_id),
                )
        conn.commit()

    print("\n✅ Usuarios demo listos.")
    for u in USERS:
        print(f"  {u['role']:<12} {u['email']:<32} password: {u['password']}")


if __name__ == "__main__":
    main()
