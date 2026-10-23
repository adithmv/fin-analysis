"""Small Supabase client factory; no business logic."""
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client
from supabase.lib.client_options import SyncClientOptions


@lru_cache(maxsize=1)
def get_client():
    load_dotenv(Path(__file__).resolve().parents[2] / '.env')
    url = os.environ.get('SUPABASE_URL', '').strip()
    key = os.environ.get('SUPABASE_SERVICE_KEY', '').strip()
    if not url or not key:
        raise ValueError('Set SUPABASE_URL and SUPABASE_SERVICE_KEY in the root .env file')
    return create_client(url, key, options=SyncClientOptions(
        postgrest_client_timeout=20, auto_refresh_token=False, persist_session=False,
    ))


def bulk_upsert(client, table, rows, on_conflict, batch_size=500):
    if batch_size < 1:
        raise ValueError('batch_size must be positive')
    written = 0
    for offset in range(0, len(rows), batch_size):
        batch = rows[offset:offset + batch_size]
        client.table(table).upsert(batch, on_conflict=on_conflict).execute()
        written += len(batch)
    return written
