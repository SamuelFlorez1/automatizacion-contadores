"""Render de HTML → PDF con WeasyPrint y helpers Jinja2 para plantillas."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _cop(v: Any) -> str:
    if v in (None, ""):
        return "$0"
    try:
        d = Decimal(str(v))
    except Exception:
        return f"${v}"
    sign = "-" if d < 0 else ""
    d = abs(d)
    entero = int(d)
    return f"{sign}${entero:,}".replace(",", ".")


def _fmt_date(v: Any) -> str:
    if v is None or v == "":
        return "—"
    return str(v)[:10]


def _pct(v: Any) -> str:
    if v is None:
        return "—"
    try:
        d = Decimal(str(v))
    except Exception:
        return "—"
    signo = "+" if d >= 0 else ""
    return f"{signo}{d:.1f}%"


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["cop"] = _cop
    env.filters["fmt_date"] = _fmt_date
    env.filters["pct"] = _pct
    return env


def render_html(template_name: str, ctx: dict[str, Any]) -> str:
    return _env().get_template(template_name).render(**ctx)


def html_to_pdf(html: str, *, base_url: str | None = None) -> bytes:
    """WeasyPrint es import-heavy; se importa on demand para no cargar
    libpango en cada startup de FastAPI/tests."""
    from weasyprint import HTML  # type: ignore

    return HTML(string=html, base_url=base_url or str(TEMPLATES_DIR)).write_pdf()


def render_pdf(template_name: str, ctx: dict[str, Any]) -> bytes:
    return html_to_pdf(render_html(template_name, ctx))
