class LLMError(Exception):
    """Base exception for all LLM adapter operations."""
    pass


class CacheMissError(LLMError):
    """Raised in replay mode when a requested prompt and input is not cached."""
    pass


class SchemaValidationError(LLMError):
    """Raised when LLM output repeatedly fails Pydantic schema validation."""
    pass


class LLMProviderError(LLMError):
    """Raised when an external LLM provider API call fails."""
    pass
