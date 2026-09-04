"""Supabase client factory with graceful fallback."""

from functools import lru_cache
from typing import Optional
from supabase import Client, create_client

from app.config.settings import get_settings


@lru_cache
def get_supabase() -> Optional[Client]:
    """Return Supabase client if configured, otherwise None."""
    settings = get_settings()
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return None
    try:
        return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    except Exception as e:
        print(f"[WARNING] Could not initialize Supabase client: {e}", flush=True)
        return None
