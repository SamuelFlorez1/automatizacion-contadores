"""Validadores: NIT (dígito de verificación), CUFE y hashes para duplicados."""

from __future__ import annotations

import hashlib
import re

NIT_WEIGHTS = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]

_CUFE_SHA384 = re.compile(r"^[0-9a-f]{96}$")
_CUFE_SEED = re.compile(r"^[0-9a-f]{64}$")


def nit_dv(nit: str) -> int:
    """Dígito de verificación de un NIT colombiano (algoritmo DIAN)."""
    digits = [int(c) for c in reversed(nit)]
    if len(digits) > len(NIT_WEIGHTS):
        raise ValueError("NIT demasiado largo")
    total = sum(d * NIT_WEIGHTS[i] for i, d in enumerate(digits))
    r = total % 11
    return r if r < 2 else 11 - r  # residuo 0 → 0, residuo 1 → 1


def normalize_nit(raw: str | None) -> str | None:
    """Deja solo dígitos (quita puntos, guiones y DV si viene como '900123456-7' → '900123456')."""
    if not raw:
        return None
    base = raw.strip().split("-")[0]
    digits = re.sub(r"\D", "", base)
    return digits or None


def validate_nit(nit: str | None, dv: int | str | None) -> bool:
    if not nit or dv is None or not nit.isdigit():
        return False
    try:
        return nit_dv(nit) == int(dv)
    except ValueError:
        return False


def cufe_kind(cufe: str | None) -> str:
    """'official' (sha384, 96 hex), 'seed' (sha256, 64 hex, sintético del seed) o 'invalid'.

    No recalcula el CUFE oficial: requiere clave técnica y datos que no están en el XML.
    """
    if not cufe:
        return "invalid"
    c = cufe.strip().lower()
    if _CUFE_SHA384.match(c):
        return "official"
    if _CUFE_SEED.match(c):
        return "seed"
    return "invalid"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dedupe_key(content: bytes) -> str:
    """Clave de idempotencia por contenido: el mismo archivo por cualquier canal es un duplicado."""
    return sha256_hex(content)
