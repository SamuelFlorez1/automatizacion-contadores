"""Validación del JWT de Supabase y carga del perfil (rol, firm, client)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import get_settings
from app.db.client import get_service_client

bearer = HTTPBearer(auto_error=False)


@lru_cache
def _jwks() -> dict[str, dict]:
    """Claves públicas de firma de Supabase (ES256), por kid."""
    url = f"{get_settings().supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    r = httpx.get(url, timeout=10)
    r.raise_for_status()
    return {k["kid"]: k for k in r.json()["keys"]}


def _decode(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    if header.get("alg") == "HS256":  # proyectos con secreto legado
        return jwt.decode(token, get_settings().supabase_jwt_secret, algorithms=["HS256"], audience="authenticated")
    key = _jwks().get(header.get("kid"))
    if key is None:
        _jwks.cache_clear()  # rotación de claves
        key = _jwks().get(header.get("kid"))
    if key is None:
        raise JWTError("kid desconocido")
    return jwt.decode(token, key, algorithms=[header["alg"]], audience="authenticated")


@dataclass
class CurrentUser:
    id: str
    firm_id: str
    role: str
    client_id: str | None

    @property
    def is_staff(self) -> bool:
        return self.role in ("firm_admin", "accountant")


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> CurrentUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta token de autenticación")
    try:
        claims = _decode(creds.credentials)
    except (JWTError, httpx.HTTPError) as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado") from e
    rows = (
        get_service_client().table("users").select("id, firm_id, role, client_id")
        .eq("id", claims["sub"]).execute().data
    )
    if not rows:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Usuario sin perfil en el despacho")
    return CurrentUser(**rows[0])
