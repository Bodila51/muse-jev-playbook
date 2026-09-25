from __future__ import annotations

import json
import logging
import math
from typing import Any

import httpx2
from typesafe_sdk import RetryPolicy, TypeSafeClient

from src.secrets import require_credential


TYPESAFE_OFFICIAL = "typesafe_official"
EXPERIENTIALLABS_NATIVE = "experientiallabs_native"
OFFICIAL_BASE_URL = "https://api.typesafe.ai"
NATIVE_BASE_URL = "https://api.experientiallabs.ai"
NATIVE_CREDENTIAL_ENV = "HERMES_CUSTOM_API_EXPERIENTIALLABS_AI_API_KEY"
NATIVE_SERVED_PROVIDER = "typesafe"
DEFAULT_TIMEOUT = 5.0
DEFAULT_MAX_RETRIES = 1
MIN_TIMEOUT = 0.1
MAX_TIMEOUT = 30.0
MAX_RETRIES = 1

# The SDK's INFO/WARNING records include provider-controlled answer names and
# types. This integration exposes bounded project diagnostics instead.
logging.getLogger("typesafe_sdk").setLevel(logging.CRITICAL + 1)


class JevConfigurationError(RuntimeError):
    """The selected provider or its explicit route is invalid."""


class JevResponseError(RuntimeError):
    """A typed Jev response failed the project's response contract."""


def _route(provider: str, base_url: str | None, credential_env: str | None) -> tuple[str, str]:
    if provider == TYPESAFE_OFFICIAL:
        resolved_base = base_url or OFFICIAL_BASE_URL
        resolved_credential_env = credential_env or "TYPESAFE_API_KEY"
        if resolved_base != OFFICIAL_BASE_URL or resolved_credential_env != "TYPESAFE_API_KEY":
            raise JevConfigurationError("official route configuration mismatch")
        return resolved_base, resolved_credential_env
    if provider == EXPERIENTIALLABS_NATIVE:
        resolved_base = base_url or NATIVE_BASE_URL
        resolved_credential_env = credential_env or NATIVE_CREDENTIAL_ENV
        if resolved_base != NATIVE_BASE_URL or resolved_credential_env != NATIVE_CREDENTIAL_ENV:
            raise JevConfigurationError("native route configuration mismatch")
        return resolved_base, resolved_credential_env
    raise JevConfigurationError("unknown Jev provider")


def _require_native_provenance(result: Any, provider: str) -> None:
    if provider != EXPERIENTIALLABS_NATIVE:
        return
    try:
        raw = json.loads(result.raw_http_response.content)
    except (AttributeError, TypeError, ValueError) as exc:
        raise JevResponseError("native response has no readable raw body") from exc
    if not isinstance(raw, dict) or raw.get("provider") != NATIVE_SERVED_PROVIDER:
        raise JevResponseError("native response provider provenance mismatch")


def system_one(
    state: dict[str, Any],
    questions: dict[str, Any],
    *,
    model: str,
    provider: str = TYPESAFE_OFFICIAL,
    base_url: str | None = None,
    credential_env: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    transport: httpx2.BaseTransport | None = None,
) -> Any:
    """Answer questions through one explicitly selected official or native route."""
    if (
        not isinstance(timeout, (int, float))
        or isinstance(timeout, bool)
        or not math.isfinite(float(timeout))
        or not MIN_TIMEOUT <= float(timeout) <= MAX_TIMEOUT
    ):
        raise JevConfigurationError("timeout must be finite and within project bounds")
    if (
        not isinstance(max_retries, int)
        or isinstance(max_retries, bool)
        or not 0 <= max_retries <= MAX_RETRIES
    ):
        raise JevConfigurationError("max_retries must be within project bounds")
    resolved_base, resolved_credential_env = _route(provider, base_url, credential_env)
    api_key = require_credential(resolved_credential_env)
    retry = RetryPolicy(
        max_retries=max_retries,
        backoff_initial=0.1,
        backoff_max=0.1,
        backoff_jitter=0.0,
        timeout=min(MAX_TIMEOUT, float(timeout) * (max_retries + 1)),
    )
    with TypeSafeClient(
        api_key=api_key,
        base_url=resolved_base,
        model=model,
        retry=retry,
        timeout=float(timeout),
        transport=transport,
    ) as client:
        result = client.system_one(state=state, questions=questions, model=model)
    _require_native_provenance(result, provider)
    return result
