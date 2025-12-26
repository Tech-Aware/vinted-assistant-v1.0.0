# domain/ai_status.py
from __future__ import annotations

from enum import Enum


class AIResultStatus(str, Enum):
    OK = "ok"

    # erreurs IA/format
    PARSE_ERROR = "parse_error"
    SCHEMA_ERROR = "schema_error"
    EMPTY_RESPONSE = "empty_response"
    REFUSAL = "refusal"

    # erreurs infra
    API_ERROR = "api_error"
    INTERNAL_ERROR = "internal_error"

    # dégradations
    FALLBACK_USED = "fallback_used"
