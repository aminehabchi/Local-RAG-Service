from __future__ import annotations

import logging

from database.postgres_service import update_file_status, update_file_chunk_count
from database.ingestion.chunking import extract_pages, build_records
from database.ingestion.cleaning import clean_pages
from database.ingestion.embedding_inserting import embed_and_insert

_log = logging.getLogger(__name__)


def ingest_and_store(file_path: str, file_id: int) -> None:
    try:
        update_file_status(file_id, "processing")
        
        raw_pages     = extract_pages(file_path)
        cleaned_pages = clean_pages(raw_pages)
        records       = build_records(cleaned_pages)

        if not records:
            update_file_chunk_count(file_id, 0)
            update_file_status(file_id, "ready")
            return

        embed_and_insert(file_id, records)
        update_file_status(file_id, "ready")

    except Exception:
        _log.exception("Ingestion failed for file_id=%s", file_id)
        update_file_status(file_id, "error")
