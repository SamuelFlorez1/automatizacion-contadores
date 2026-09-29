"""Endpoints de reportes PDF.

- GET /reports/monthly/{client_id}/{period}    — período 'YYYY-MM'
- GET /reports/iva/{client_id}/{period_label}  — período tal cual del calendario ('jul-ago-2026')

Los dos devuelven `application/pdf`. Un query param `?format=html` sirve la
versión HTML sin invocar WeasyPrint (útil para debug/dev).
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.concurrency import run_in_threadpool
from starlette.responses import HTMLResponse, Response

from app.auth import CurrentUser, get_current_user
from app.db.client import get_service_client
from app.reports import iva_form300 as iva_mod
from app.reports import monthly as monthly_mod
from app.reports.narrative import generate_narrative
from app.reports.pdf import html_to_pdf, render_html

router = APIRouter(prefix="/reports", tags=["reports"])


def _authorize(db, user: CurrentUser, client_id: str) -> None:
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(403, "Solo puedes consultar tu propia cuenta")
    rows = db.table("clients").select("id").eq("id", client_id).eq("firm_id", user.firm_id).execute().data
    if not rows:
        raise HTTPException(404, "Cliente no encontrado")


def _pdf_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/monthly/{client_id}/{period}")
async def monthly_report(
    client_id: str,
    period: str,
    format: str = Query("pdf", pattern="^(pdf|html)$"),
    with_narrative: bool = True,
    user: CurrentUser = Depends(get_current_user),
) -> Response:
    db = get_service_client()
    _authorize(db, user, client_id)
    try:
        monthly_mod.parse_period(period)
    except Exception:
        raise HTTPException(400, "Período inválido, usa formato YYYY-MM")

    ds = await run_in_threadpool(
        monthly_mod.fetch_and_build,
        db, firm_id=user.firm_id, client_id=client_id, period=period,
    )
    if with_narrative:
        ds.narrative = await run_in_threadpool(generate_narrative, ds)

    html = render_html("monthly.html", {"ds": ds, "generated_at": ds.generated_at.isoformat()})
    if format == "html":
        return HTMLResponse(html)
    pdf = await run_in_threadpool(html_to_pdf, html)
    fname = f"reporte-{period}-{client_id[:8]}.pdf"
    return _pdf_response(pdf, fname)


@router.get("/iva/{client_id}/{period_label}")
async def iva_report(
    client_id: str,
    period_label: str,
    format: str = Query("pdf", pattern="^(pdf|html)$"),
    user: CurrentUser = Depends(get_current_user),
) -> Response:
    db = get_service_client()
    _authorize(db, user, client_id)
    try:
        ds = await run_in_threadpool(
            iva_mod.fetch_and_build,
            db, firm_id=user.firm_id, client_id=client_id, period_label=period_label,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    html = render_html("iva_form300.html", {"ds": ds, "generated_at": date.today().isoformat()})
    if format == "html":
        return HTMLResponse(html)
    pdf = await run_in_threadpool(html_to_pdf, html)
    fname = f"iva-form300-{period_label}-{client_id[:8]}.pdf"
    return _pdf_response(pdf, fname)
