"""Endpoints de cálculo fiscal.

- POST /tax/generate/{client_id}                   → recalcula y persiste obligaciones del año.
- GET  /tax/calculate/{client_id}/{period_label}   → devuelve la(s) obligación(es) de ese período.
- GET  /tax/obligations/{client_id}                → lista obligaciones ya persistidas.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth import CurrentUser, get_current_user
from app.db.client import get_service_client
from app.tax.obligations import generate_and_persist

router = APIRouter(prefix="/tax", tags=["tax"])


def _authorize(db, user: CurrentUser, client_id: str) -> None:
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(403, "Solo puedes consultar tu propia cuenta")
    rows = db.table("clients").select("id").eq("id", client_id).eq("firm_id", user.firm_id).execute().data
    if not rows:
        raise HTTPException(404, "Cliente no encontrado")


@router.post("/generate/{client_id}")
def generate_endpoint(
    client_id: str,
    year: int = 2026,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    if not user.is_staff:
        raise HTTPException(403, "Solo el equipo del despacho puede generar obligaciones")
    db = get_service_client()
    _authorize(db, user, client_id)
    rows = generate_and_persist(db, firm_id=user.firm_id, client_id=client_id, year=year)
    return {"generated": len(rows), "year": year}


@router.get("/calculate/{client_id}/{period_label}")
def calculate_endpoint(
    client_id: str,
    period_label: str,
    year: int = 2026,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    db = get_service_client()
    _authorize(db, user, client_id)
    rows = generate_and_persist(
        db, firm_id=user.firm_id, client_id=client_id, year=year, period_label=period_label,
    )
    if not rows:
        raise HTTPException(404, f"No aplica ninguna obligación con período '{period_label}'")
    return {"period_label": period_label, "obligations": rows}


@router.get("/obligations/{client_id}")
def list_obligations(
    client_id: str,
    year: int = 2026,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    db = get_service_client()
    _authorize(db, user, client_id)
    rows = (
        db.table("tax_obligations")
        .select("kind, period_label, period_start, period_end, due_date, amount, status, calculation_snapshot")
        .eq("client_id", client_id)
        .gte("period_start", f"{year}-01-01").lte("period_start", f"{year}-12-31")
        .order("due_date").execute().data
    )
    return {"count": len(rows), "obligations": rows}
