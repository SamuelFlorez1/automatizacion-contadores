"""Narrativa opcional en español generada por Sonnet 5 para el reporte mensual.

Sin `ANTHROPIC_API_KEY` o si Anthropic falla, se devuelve una narrativa
determinística basada en las cifras del dataset.
"""

from __future__ import annotations

from decimal import Decimal

import structlog

from app.config import get_settings

log = structlog.get_logger()

MAX_TOKENS = 400


def _fallback(ds) -> str:
    inc = ds.income_statement
    trozos = [
        f"Durante {ds.period_label.lower()} {ds.client.get('legal_name', 'el cliente')} "
        f"registró ingresos por {_cop(inc.ingresos)} y gastos operativos por "
        f"{_cop(inc.gastos)}, con utilidad operacional de {_cop(inc.utilidad_operacional)}."
    ]
    if ds.variation_utilidad is not None:
        d = Decimal(str(ds.variation_utilidad))
        signo = "aumentó" if d >= 0 else "disminuyó"
        trozos.append(f"La utilidad {signo} {abs(d):.1f}% respecto al mes anterior.")
    if ds.cash_flow.neto < 0:
        trozos.append(f"El flujo de caja fue negativo por {_cop(-ds.cash_flow.neto)}.")
    if ds.top_expenses:
        top = ds.top_expenses[0]
        trozos.append(
            f"El mayor proveedor del mes fue {top.proveedor} con {_cop(top.total)} "
            f"en {top.n_facturas} factura(s)."
        )
    return " ".join(trozos)


def _cop(v) -> str:
    try:
        d = Decimal(str(v))
    except Exception:
        return f"${v}"
    return f"${int(abs(d)):,}".replace(",", ".")


def generate_narrative(ds) -> str:
    """Devuelve un párrafo (2-4 frases) resumiendo el mes.
    - Sin API key → texto determinístico.
    - Con API key → Sonnet 5 en español, tono ejecutivo, sin tecnicismos.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        return _fallback(ds)

    try:
        from anthropic import Anthropic
    except Exception:
        return _fallback(ds)

    inc = ds.income_statement
    resumen = (
        f"Cliente: {ds.client.get('legal_name')}\n"
        f"Período: {ds.period_label}\n"
        f"Ingresos: {inc.ingresos}\nCostos: {inc.costos}\nGastos: {inc.gastos}\n"
        f"Utilidad operacional: {inc.utilidad_operacional}\n"
        f"IVA generado: {inc.iva_generado}\nIVA descontable: {inc.iva_descontable}\n"
        f"Flujo caja neto: {ds.cash_flow.neto}\n"
        f"Variación utilidad vs mes anterior: {ds.variation_utilidad}%\n"
        f"Top gasto: "
        + (f"{ds.top_expenses[0].proveedor} ({ds.top_expenses[0].total})" if ds.top_expenses else "N/A")
    )
    prompt = (
        "Eres un contador colombiano redactando el resumen ejecutivo del reporte "
        "mensual de un cliente. Escribe 2-4 frases, en español, tono ejecutivo, "
        "sin tecnicismos, resaltando lo relevante del mes. No incluyas cifras "
        "que no estén en los datos. No inventes recomendaciones fiscales.\n\n"
        f"Datos:\n{resumen}"
    )
    try:
        client = Anthropic(api_key=settings.anthropic_api_key)
        resp = client.messages.create(
            model=settings.model_sonnet,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
        return text or _fallback(ds)
    except Exception as e:
        log.warning("narrative_failed", error=str(e))
        return _fallback(ds)
