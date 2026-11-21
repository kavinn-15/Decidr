import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypeVar, Union
import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.llm.exceptions import CacheMissError, SchemaValidationError, LLMProviderError

logger = logging.getLogger("decidr.llm")

T = TypeVar("T", bound=BaseModel)

# Default cache directory in backend
DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".llm_cache"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def get_cache_key(model: str, rendered_prompt: str, variables: Dict[str, Any]) -> str:
    """Generate SHA256 cache key from model, rendered prompt, and inputs."""
    hasher = hashlib.sha256()
    hasher.update(model.encode("utf-8"))
    hasher.update(b"::")
    hasher.update(rendered_prompt.encode("utf-8"))
    hasher.update(b"::")
    serialized_inputs = json.dumps(variables, sort_keys=True, default=str)
    hasher.update(serialized_inputs.encode("utf-8"))
    return hasher.hexdigest()


def load_prompt_template(prompt_name: str) -> tuple[str, str]:
    """
    Load a versioned prompt template from llm/prompts/.
    Returns (version, template_text).
    """
    # Look for {prompt_name}, {prompt_name}.txt, or {prompt_name}.v1.txt
    candidates = [
        PROMPTS_DIR / prompt_name,
        PROMPTS_DIR / f"{prompt_name}.txt",
        PROMPTS_DIR / f"{prompt_name}.v1.txt",
    ]
    matched_path = None
    for p in candidates:
        if p.exists():
            matched_path = p
            break

    if not matched_path:
        # Check glob
        matches = list(PROMPTS_DIR.glob(f"{prompt_name}*"))
        if matches:
            matched_path = matches[0]

    if not matched_path or not matched_path.exists():
        raise FileNotFoundError(f"Prompt template '{prompt_name}' not found in {PROMPTS_DIR}")

    raw_content = matched_path.read_text(encoding="utf-8")
    lines = raw_content.splitlines()

    version = "1.0.0"
    content_lines = []
    for line in lines:
        if line.startswith("# Version:"):
            version = line.split(":", 1)[1].strip()
        elif line.startswith("#"):
            continue
        else:
            content_lines.append(line)

    template = "\n".join(content_lines).strip()
    return version, template


def clean_json_markdown(text: str) -> str:
    """Strip markdown code fences from JSON output if present."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


class LLMAdapter:
    """
    Decidr LLM Adapter.
    - All model calls go through complete_json.
    - Temperature is 0.
    - Deterministic disk cache keyed by SHA256(model, prompt, input).
    - Supports fake, gemini, and anthropic providers.
    - Retries up to 2 times on schema validation errors with feedback.
    - Logs model, latency, and token counts.
    """

    def __init__(self, cache_dir: Path = DEFAULT_CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.fake_registry: Dict[str, Any] = {}
        self.fake_queue: list[Any] = []

    def register_fake_response(self, key_or_prompt: str, response: Union[dict, str, BaseModel]) -> None:
        """Register a fixture for the fake provider."""
        if isinstance(response, BaseModel):
            self.fake_registry[key_or_prompt] = response.model_dump()
        elif isinstance(response, str):
            self.fake_registry[key_or_prompt] = response
        else:
            self.fake_registry[key_or_prompt] = response

    def enqueue_fake_response(self, response: Union[dict, str, BaseModel]) -> None:
        """Enqueue sequential responses for testing retries."""
        if isinstance(response, BaseModel):
            self.fake_queue.append(json.dumps(response.model_dump()))
        elif isinstance(response, dict):
            self.fake_queue.append(json.dumps(response))
        else:
            self.fake_queue.append(response)

    def _read_cache(self, key: str) -> Optional[dict]:
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error reading cache file {cache_file}: {e}")
        return None

    def _write_cache(self, key: str, payload: dict[str, Any]) -> None:
        cache_file = self.cache_dir / f"{key}.json"
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def _call_fake(self, prompt_name: str, rendered_prompt: str, schema: Type[T]) -> tuple[str, dict]:
        """Return fixture response or synthesize valid minimal JSON matching schema."""
        if self.fake_queue:
            raw_text = self.fake_queue.pop(0)
            return raw_text, {"prompt_tokens": 50, "completion_tokens": 50, "total_tokens": 100}

        if prompt_name in self.fake_registry:
            reg = self.fake_registry[prompt_name]
            raw_text = json.dumps(reg) if isinstance(reg, (dict, list)) else str(reg)
            return raw_text, {"prompt_tokens": 50, "completion_tokens": 50, "total_tokens": 100}

        # Synthesize fallback JSON based on schema fields
        mock_obj = {}
        for fname, field in schema.model_fields.items():
            ann = field.annotation
            if ann is str or str in getattr(ann, "__args__", ()):
                mock_obj[fname] = "mock_value"
            elif ann is int or int in getattr(ann, "__args__", ()):
                mock_obj[fname] = 1
            elif ann is float or float in getattr(ann, "__args__", ()):
                mock_obj[fname] = 1.0
            elif ann is bool or bool in getattr(ann, "__args__", ()):
                mock_obj[fname] = True
            elif getattr(ann, "__origin__", None) is list:
                mock_obj[fname] = []
            elif getattr(ann, "__origin__", None) is dict:
                mock_obj[fname] = {}
            else:
                mock_obj[fname] = None

        return json.dumps(mock_obj), {"prompt_tokens": 50, "completion_tokens": 50, "total_tokens": 100}

    def _call_gemini(self, model: str, prompt: str) -> tuple[str, dict]:
        """Call Gemini API via HTTP with temperature 0."""
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise LLMProviderError("GEMINI_API_KEY is not set.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json",
            },
        }

        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code != 200:
                raise LLMProviderError(f"Gemini API returned status {resp.status_code}: {resp.text}")
            data = resp.json()

        try:
            candidate = data["candidates"][0]["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
            tokens = {
                "prompt_tokens": usage.get("promptTokenCount", 0),
                "completion_tokens": usage.get("candidatesTokenCount", 0),
                "total_tokens": usage.get("totalTokenCount", 0),
            }
            return candidate, tokens
        except (KeyError, IndexError) as e:
            raise LLMProviderError(f"Unexpected Gemini response structure: {data}") from e

    def _call_anthropic(self, model: str, prompt: str) -> tuple[str, dict]:
        """Call Anthropic API via HTTP with temperature 0."""
        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            raise LLMProviderError("ANTHROPIC_API_KEY is not set.")

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": 4096,
            "temperature": 0.0,
            "messages": [{"role": "user", "content": prompt}],
        }

        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise LLMProviderError(f"Anthropic API returned status {resp.status_code}: {resp.text}")
            data = resp.json()

        try:
            content = data["content"][0]["text"]
            usage = data.get("usage", {})
            tokens = {
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            }
            return content, tokens
        except (KeyError, IndexError) as e:
            raise LLMProviderError(f"Unexpected Anthropic response structure: {data}") from e

    def complete_json(
        self,
        prompt_name: str,
        variables: Dict[str, Any],
        schema: Type[T],
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> T:
        """
        Execute an LLM completion returning a validated Pydantic object.
        - Temperature 0.
        - Caches responses on disk.
        - Retries up to 2 times on schema validation failure with error feedback.
        - Enforces replay mode cache check.
        """
        model_name = model or settings.LLM_MODEL
        provider_name = provider or settings.LLM_PROVIDER
        mode = settings.LLM_MODE.lower()

        # Load versioned template
        version, template = load_prompt_template(prompt_name)

        # Render template
        try:
            rendered_prompt = template.format(**variables)
        except KeyError as e:
            raise ValueError(f"Missing variable {e} for prompt template '{prompt_name}'")

        # Compute SHA256 cache key
        cache_key = get_cache_key(model_name, rendered_prompt, variables)

        # In cache or replay mode, check disk first
        cached = self._read_cache(cache_key)
        if cached is not None and mode in ("live", "record", "replay", "cache"):
            logger.info(f"LLM cache HIT [key={cache_key[:8]}, prompt={prompt_name}]")
            return schema.model_validate(cached["response_json"])

        if mode == "replay":
            raise CacheMissError(
                f"Cache miss in replay mode for prompt '{prompt_name}' (model='{model_name}', key='{cache_key[:8]}')."
            )

        # Schema JSON instructions
        schema_json_desc = json.dumps(schema.model_json_schema(), indent=2)
        full_prompt = (
            f"{rendered_prompt}\n\n"
            f"You MUST respond ONLY with a JSON object strictly matching this JSON Schema:\n"
            f"{schema_json_desc}"
        )

        max_retries = 2
        last_error = None
        attempt_prompt = full_prompt

        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.warning(f"Retrying LLM completion (attempt {attempt}/{max_retries}) due to: {last_error}")
                attempt_prompt = (
                    f"{full_prompt}\n\n"
                    f"CRITICAL: Your previous response failed schema validation with error:\n"
                    f"{last_error}\n"
                    f"Please correct the error and return strictly valid JSON conforming to the schema."
                )

            t0 = time.perf_counter()

            # Invoke provider
            if provider_name == "fake":
                raw_text, tokens = self._call_fake(prompt_name, attempt_prompt, schema)
            elif provider_name == "gemini":
                raw_text, tokens = self._call_gemini(model_name, attempt_prompt)
            elif provider_name == "anthropic":
                raw_text, tokens = self._call_anthropic(model_name, attempt_prompt)
            else:
                raise LLMProviderError(f"Unsupported LLM_PROVIDER: {provider_name}")

            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.info(
                f"LLM call [{provider_name}/{model_name}] latency={latency_ms}ms tokens={tokens} attempt={attempt}"
            )

            # Clean and parse JSON
            cleaned_text = clean_json_markdown(raw_text)
            try:
                parsed_data = json.loads(cleaned_text)
            except json.JSONDecodeError as err:
                last_error = f"Invalid JSON format: {err}"
                continue

            # Validate against Pydantic schema
            try:
                validated_obj = schema.model_validate(parsed_data)

                # Store in disk cache
                cache_payload = {
                    "model": model_name,
                    "provider": provider_name,
                    "prompt_name": prompt_name,
                    "prompt_version": version,
                    "variables": variables,
                    "raw_response": raw_text,
                    "response_json": validated_obj.model_dump(mode="json"),
                    "latency_ms": latency_ms,
                    "token_counts": tokens,
                }
                self._write_cache(cache_key, cache_payload)
                return validated_obj

            except ValidationError as v_err:
                last_error = str(v_err)

        raise SchemaValidationError(
            f"LLM output for '{prompt_name}' failed validation after {max_retries} retries. Error: {last_error}"
        )


adapter = LLMAdapter()


def complete_json(
    prompt_name: str,
    variables: Dict[str, Any],
    schema: Type[T],
    model: Optional[str] = None,
    provider: Optional[str] = None,
) -> T:
    """Convenience wrapper for the default LLM adapter."""
    return adapter.complete_json(prompt_name, variables, schema, model=model, provider=provider)
