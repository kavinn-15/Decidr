import shutil
import tempfile
from pathlib import Path
import pytest
from pydantic import BaseModel, Field

from app.core.config import settings
from app.llm.adapter import LLMAdapter
from app.llm.exceptions import CacheMissError, SchemaValidationError


class DummyResult(BaseModel):
    decision: str
    confidence: float


def test_cache_hit_avoids_second_call():
    """
    Assert that the first call writes to cache, and the second call reads from cache
    without invoking the provider a second time.
    """
    temp_cache_dir = Path(tempfile.mkdtemp())
    try:
        adapter = LLMAdapter(cache_dir=temp_cache_dir)
        original_mode = settings.LLM_MODE
        original_provider = settings.LLM_PROVIDER
        settings.LLM_MODE = "live"
        settings.LLM_PROVIDER = "fake"

        # Provide exactly one response in queue
        adapter.enqueue_fake_response({"decision": "Adopt Provider A", "confidence": 0.99})

        vars_input = {"project": "Payments", "date": "2026-11-02", "transcript": "We will use Provider A."}

        # 1. First call uses the fake response from queue
        res1 = adapter.complete_json("extract_items", vars_input, DummyResult)
        assert res1.decision == "Adopt Provider A"
        assert len(adapter.fake_queue) == 0  # Queue is now empty!

        # 2. Second call must hit cache (if it called provider, queue is empty so it would synthesize a mock)
        res2 = adapter.complete_json("extract_items", vars_input, DummyResult)
        assert res2.decision == "Adopt Provider A"
        assert res2.confidence == 0.99

    finally:
        settings.LLM_MODE = original_mode
        settings.LLM_PROVIDER = original_provider
        shutil.rmtree(temp_cache_dir, ignore_errors=True)


def test_replay_miss_raises():
    """
    Assert that when LLM_MODE is 'replay', a cache miss raises CacheMissError.
    """
    temp_cache_dir = Path(tempfile.mkdtemp())
    try:
        adapter = LLMAdapter(cache_dir=temp_cache_dir)
        original_mode = settings.LLM_MODE
        settings.LLM_MODE = "replay"

        with pytest.raises(CacheMissError) as exc_info:
            adapter.complete_json(
                "extract_items",
                {"project": "Uncached", "date": "2026-11-02", "transcript": "Some text"},
                DummyResult,
            )
        assert "Cache miss in replay mode" in str(exc_info.value)

    finally:
        settings.LLM_MODE = original_mode
        shutil.rmtree(temp_cache_dir, ignore_errors=True)


def test_schema_failure_retries_and_succeeds():
    """
    Assert that if LLM returns invalid JSON/schema, it retries up to 2 times.
    If a subsequent retry succeeds, the validated object is returned.
    """
    temp_cache_dir = Path(tempfile.mkdtemp())
    try:
        adapter = LLMAdapter(cache_dir=temp_cache_dir)
        original_mode = settings.LLM_MODE
        original_provider = settings.LLM_PROVIDER
        settings.LLM_MODE = "live"
        settings.LLM_PROVIDER = "fake"

        # Attempt 0: Invalid JSON
        adapter.enqueue_fake_response("NOT VALID JSON AT ALL")
        # Attempt 1: Valid JSON but missing required fields
        adapter.enqueue_fake_response({"wrong_field": "oops"})
        # Attempt 2: Valid schema
        adapter.enqueue_fake_response({"decision": "Fixed on retry", "confidence": 0.88})

        vars_input = {"project": "RetryTest", "date": "2026-11-02", "transcript": "Retry transcript"}
        result = adapter.complete_json("extract_items", vars_input, DummyResult)

        assert result.decision == "Fixed on retry"
        assert result.confidence == 0.88
        assert len(adapter.fake_queue) == 0

    finally:
        settings.LLM_MODE = original_mode
        settings.LLM_PROVIDER = original_provider
        shutil.rmtree(temp_cache_dir, ignore_errors=True)


def test_schema_failure_exhausts_retries_and_raises():
    """
    Assert that if schema validation fails on all 3 attempts (initial + 2 retries),
    SchemaValidationError is raised.
    """
    temp_cache_dir = Path(tempfile.mkdtemp())
    try:
        adapter = LLMAdapter(cache_dir=temp_cache_dir)
        original_mode = settings.LLM_MODE
        original_provider = settings.LLM_PROVIDER
        settings.LLM_MODE = "live"
        settings.LLM_PROVIDER = "fake"

        # Enqueue 3 bad responses
        adapter.enqueue_fake_response("Bad 1")
        adapter.enqueue_fake_response("Bad 2")
        adapter.enqueue_fake_response("Bad 3")

        vars_input = {"project": "ExhaustTest", "date": "2026-11-02", "transcript": "Fail transcript"}

        with pytest.raises(SchemaValidationError) as exc_info:
            adapter.complete_json("extract_items", vars_input, DummyResult)

        assert "failed validation after 2 retries" in str(exc_info.value)

    finally:
        settings.LLM_MODE = original_mode
        settings.LLM_PROVIDER = original_provider
        shutil.rmtree(temp_cache_dir, ignore_errors=True)
