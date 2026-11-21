import logging
import uuid
from pathlib import Path
from typing import Optional
import httpx

from app.core.config import settings

logger = logging.getLogger("decidr.storage")


def upload_transcript_file(
    content_bytes: bytes,
    original_filename: str,
    project: str,
    content_type: str = "text/plain",
) -> str:
    """
    Stores an uploaded meeting transcript.
    - If Supabase Storage credentials (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY)
      are configured, uploads the object to the configured bucket (default 'decidr-transcripts').
    - If Supabase Storage is not configured (e.g. local dev, test, or SQLite mode),
      returns the sanitized filename reference, preserving existing database-native utterance storage.
    """
    sanitized_name = Path(original_filename).name
    unique_suffix = uuid.uuid4().hex[:8]
    object_path = f"{project}/{unique_suffix}_{sanitized_name}"

    supabase_url = settings.SUPABASE_URL
    api_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY

    if not supabase_url or not api_key:
        logger.info(f"Supabase Storage not configured. Storing reference locally as '{sanitized_name}'.")
        return sanitized_name

    # Upload to Supabase Storage REST endpoint
    base_url = supabase_url.rstrip("/")
    bucket = settings.SUPABASE_STORAGE_BUCKET
    endpoint = f"{base_url}/storage/v1/object/{bucket}/{object_path}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": content_type,
        "x-upsert": "true",
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(endpoint, content=content_bytes, headers=headers)
            if resp.status_code in (200, 201):
                logger.info(f"Successfully uploaded transcript to Supabase Storage: {object_path}")
                return f"supabase://{bucket}/{object_path}"
            elif resp.status_code == 404:
                logger.warning(
                    f"Supabase Storage bucket '{bucket}' does not exist or is inaccessible (HTTP 404). "
                    "Falling back to local reference."
                )
                return sanitized_name
            else:
                logger.warning(
                    f"Supabase Storage upload returned HTTP {resp.status_code}: {resp.text}. "
                    "Falling back to local reference."
                )
                return sanitized_name
    except Exception as exc:
        logger.warning(f"Failed to upload to Supabase Storage ({exc}). Falling back to local reference.")
        return sanitized_name
