"""Supabase client factory.

Provides a single, lazily-created Supabase client for the repository layer.
"""
from functools import lru_cache

from supabase import Client, create_client

from app.config.settings import get_settings


@lru_cache
def get_supabase() -> Client:
    """Create (once) and return a configured Supabase client.

    Raises:
        RuntimeError: if SUPABASE_URL or SUPABASE_KEY are not configured.
    """
    settings = get_settings()
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set in the .env file. "
            "Copy .env.example to .env and fill in the values."
        )
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
