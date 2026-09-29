from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def get_service_client() -> Client:
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY deben estar definidos")
    return create_client(s.supabase_url, s.supabase_service_role_key)


def get_anon_client() -> Client:
    s = get_settings()
    if not s.supabase_url or not s.supabase_anon_key:
        raise RuntimeError("SUPABASE_URL y SUPABASE_ANON_KEY deben estar definidos")
    return create_client(s.supabase_url, s.supabase_anon_key)
