from __future__ import annotations

import io
import logging
import os
import subprocess
import sys
import unittest
from typing import Any
from unittest.mock import patch

import httpx2
from typesafe_sdk import TypeSafeAPIError

from src.jev_client import JevResponseError, system_one
from src.secrets import CredentialError


NATIVE_BASE_URL = "https://api.experientiallabs.ai"
NATIVE_CREDENTIAL_ENV = "HERMES_CUSTOM_API_EXPERIENTIALLABS_AI_API_KEY"
NATIVE_TEST_KEY = "test-native-key-not-a-secret"


def response_payload(*, provider: str = "typesafe") -> dict[str, Any]:
    return {
        "id": "evt_test_only",
        "model": "jev-latest",
        "provider": provider,
        "usage": {},
        "answers": {
            "intent": {
                "type": "choice",
                "choice": "research",
                "confidence": 0.9,
                "probabilities": {"research": 0.9, "coding": 0.1},
            },
            "reuse_cache": {"type": "noul", "noul": 0.1},
            "needs_subagent": {"type": "noul", "noul": 0.1},
            "stop_retry": {"type": "noul", "noul": 0.1},
            "complexity": {
                "type": "score",
                "score": 1.0,
                "confidence": 0.8,
                "legend": {"0": "Trivial", "1": "Normal", "2": "Heavy"},
                "probabilities": {"0": 0.1, "1": 0.8, "2": 0.1},
            },
        },
    }


class NativeRouteContractTests(unittest.TestCase):
    def test_official_sdk_uses_explicit_native_route_and_decodes_response(self) -> None:
        requests: list[httpx2.Request] = []

        def handler(request: httpx2.Request) -> httpx2.Response:
            requests.append(request)
            return httpx2.Response(200, json=response_payload())

        conflicting_env = {
            "TYPESAFE_API_KEY": "test-ambient-official-key-not-a-secret",
            "TYPESAFE_BASE_URL": "https://ambient.invalid",
            "TYPESAFE_DEFAULT_MODEL": "ambient-model",
            NATIVE_CREDENTIAL_ENV: NATIVE_TEST_KEY,
        }
        with patch.dict(os.environ, conflicting_env, clear=False):
            result = system_one(
                {"goal": "sanitized test state"},
                {"intent": {"type": "noul", "instructions": "Is this a test?"}},
                model="jev-latest",
                provider="experientiallabs_native",
                base_url=NATIVE_BASE_URL,
                credential_env=NATIVE_CREDENTIAL_ENV,
                timeout=1.0,
                max_retries=0,
                transport=httpx2.MockTransport(handler),
            )

        self.assertEqual(1, len(requests))
        self.assertEqual("POST", requests[0].method)
        self.assertEqual(f"{NATIVE_BASE_URL}/v1/systemone", str(requests[0].url))
        self.assertEqual(f"Bearer {NATIVE_TEST_KEY}", requests[0].headers["Authorization"])
        self.assertEqual("research", result.choices["intent"].choice)

    def test_missing_native_credential_is_an_ordinary_exception(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(CredentialError):
                system_one(
                    {"goal": "sanitized test state"},
                    {"intent": {"type": "noul", "instructions": "Is this a test?"}},
                    model="jev-latest",
                    provider="experientiallabs_native",
                    timeout=1.0,
                    max_retries=0,
                )

    def test_wrong_native_provider_is_rejected(self) -> None:
        def handler(request: httpx2.Request) -> httpx2.Response:
            return httpx2.Response(200, json=response_payload(provider="other"))

        with patch.dict(os.environ, {NATIVE_CREDENTIAL_ENV: NATIVE_TEST_KEY}, clear=False):
            with self.assertRaises(JevResponseError):
                system_one(
                    {"goal": "sanitized test state"},
                    {"intent": {"type": "noul", "instructions": "Is this a test?"}},
                    model="jev-latest",
                    provider="experientiallabs_native",
                    timeout=1.0,
                    max_retries=0,
                    transport=httpx2.MockTransport(handler),
                )

    def test_sdk_logger_is_disabled_after_import(self) -> None:
        with patch.dict(os.environ, {"TYPESAFE_LOG_LEVEL": "debug"}, clear=False):
            code = "import logging; from src import jev_client; print(logging.getLogger('typesafe_sdk').level)"
            completed = subprocess.run(
                [sys.executable, "-B", "-c", code],
                cwd=os.fspath(__import__("pathlib").Path(__file__).parents[1]),
                check=True,
                capture_output=True,
                text=True,
                env={**os.environ, "TYPESAFE_LOG_LEVEL": "debug"},
            )
        self.assertEqual(str(logging.CRITICAL + 1), completed.stdout.strip())

    def test_sdk_response_controlled_warning_is_not_emitted(self) -> None:
        stream = io.StringIO()
        logger = logging.getLogger("typesafe_sdk")
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)

        def handler_transport(request: httpx2.Request) -> httpx2.Response:
            payload = response_payload()
            payload["answers"]["private_answer_marker"] = {
                "type": "private_type_marker"
            }
            return httpx2.Response(200, json=payload)

        try:
            with patch.dict(os.environ, {NATIVE_CREDENTIAL_ENV: NATIVE_TEST_KEY}, clear=False):
                system_one(
                    {"goal": "sanitized test state"},
                    {"intent": {"type": "choice", "criteria": ["research"]}},
                    model="jev-latest",
                    provider="experientiallabs_native",
                    base_url=NATIVE_BASE_URL,
                    credential_env=NATIVE_CREDENTIAL_ENV,
                    timeout=1.0,
                    max_retries=0,
                    transport=httpx2.MockTransport(handler_transport),
                )
        finally:
            logger.removeHandler(handler)
        self.assertNotIn("private_answer_marker", stream.getvalue())
        self.assertNotIn("private_type_marker", stream.getvalue())

    def test_native_transport_error_is_not_hidden_inside_sdk_logger(self) -> None:
        calls = 0

        def handler(request: httpx2.Request) -> httpx2.Response:
            nonlocal calls
            calls += 1
            return httpx2.Response(503, json={"message": "test transient failure"})

        with patch.dict(os.environ, {NATIVE_CREDENTIAL_ENV: NATIVE_TEST_KEY}, clear=False):
            with self.assertRaises(TypeSafeAPIError):
                system_one(
                    {"goal": "sanitized test state"},
                    {"intent": {"type": "noul", "instructions": "Is this a test?"}},
                    model="jev-latest",
                    provider="experientiallabs_native",
                    timeout=0.1,
                    max_retries=1,
                    transport=httpx2.MockTransport(handler),
                )
        self.assertEqual(2, calls)


if __name__ == "__main__":
    unittest.main()
