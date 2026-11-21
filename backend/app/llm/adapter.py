import hashlib
import json
import os
from pathlib import Path
from typing import Any, Optional
from app.core.config import settings

CACHE_DIR = Path(".llm_cache")


def get_cache_key(model: str, prompt: str, input_text: str) -> str:
    hasher = hashlib.sha256()
    hasher.update(model.encode("utf-8"))
    hasher.update(b"::")
    hasher.update(prompt.encode("utf-8"))
    hasher.update(b"::")
    hasher.update(input_text.encode("utf-8"))
    return hasher.hexdigest()


class LLMAdapter:
    """
    All model calls go through this adapter. Temperature is 0.
    Responses are cached on disk keyed by a hash of (model, prompt, input) so
    demo runs are deterministic and work offline.
    """

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _read_cache(self, key: str) -> Optional[str]:
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("response")
        return None

    def _write_cache(self, key: str, payload: dict[str, Any]) -> None:
        cache_file = self.cache_dir / f"{key}.json"
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def generate(self, prompt: str, input_text: str, model: Optional[str] = None) -> str:
        model_name = model or settings.LLM_MODEL
        cache_key = get_cache_key(model_name, prompt, input_text)

        if settings.LLM_MODE in ("cache", "replay"):
            cached = self._read_cache(cache_key)
            if cached is not None:
                return cached
            if settings.LLM_MODE == "replay":
                raise RuntimeError(f"Cache miss in replay mode for key {cache_key}")

        # Placeholder for provider calls to be added in later tasks
        response_text = f"LLM response placeholder for {model_name}"

        self._write_cache(cache_key, {
            "model": model_name,
            "prompt": prompt,
            "input": input_text,
            "response": response_text
        })
        return response_text


adapter = LLMAdapter()
