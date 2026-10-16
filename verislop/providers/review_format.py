"""Opt-in syntax constraints for raw review ballots; never review authority."""
from __future__ import annotations

from .. import canonical, schemas
from ..errors import Diagnostic, UsageError

REVIEW_PURPOSES = frozenset({"review:interpretation", "review:formal_contract",
                           "review:implementation", "review:release"})
SCHEMA_FILE = "review-model-response.schema.json"


def ollama_review_schema() -> dict:
    """Return fresh schema bytes as an object; it contains no task-specific values."""
    try:
        value = canonical.load_file(schemas.schema_dir() / SCHEMA_FILE)
    except (OSError, ValueError) as exc:
        raise UsageError("registered review response schema is unavailable",
                         [Diagnostic("CONFIGURATION_INVALID", str(exc))]) from None
    if not isinstance(value, dict) or value.get("type") != "object":
        raise UsageError("registered review response schema is malformed",
                         [Diagnostic("CONFIGURATION_INVALID", "raw-ballot schema must be an object schema")])
    return value
