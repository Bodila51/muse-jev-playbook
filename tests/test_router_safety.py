from __future__ import annotations

import contextlib
import builtins
import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml
from typesafe_sdk import TypeSafeError

from src import config as config_module
from src import router as router_module
from src.config import load_config
from src.cli import main as cli_main


def result_stub(*, include_intent: bool = True) -> SimpleNamespace:
    choices = {}
    if include_intent:
        choices["intent"] = SimpleNamespace(
            choice="research",
            confidence=0.9,
            probabilities={"research": 0.9, "coding": 0.1},
        )
    return SimpleNamespace(
        choices=choices,
        nouls={
            "reuse_cache": SimpleNamespace(noul=0.1),
            "needs_subagent": SimpleNamespace(noul=0.1),
            "stop_retry": SimpleNamespace(noul=0.1),
        },
        scores={"complexity": SimpleNamespace(score=1.0)},
    )


def enabled_config() -> dict[str, object]:
    return {
        "enabled": True,
        "mode": "shadow",
        "model": "jev-latest",
        "provider": "experientiallabs_native",
        "base_url": "https://api.experientiallabs.ai",
        "credential_env": "HERMES_CUSTOM_API_EXPERIENTIALLABS_AI_API_KEY",
        "timeout": 1.0,
        "max_retries": 0,
        "thresholds": {
            "min_choice_confidence": 0.55,
            "reuse_min": 0.65,
            "subagent_min": 0.75,
            "stop_retry_min": 0.55,
        },
        "limits": {"max_browser_sources": 5, "max_retries_same_error": 1},
        "logging": {"path": "logs/runs.jsonl"},
    }


class ConfigFailClosedTests(unittest.TestCase):
    def test_missing_local_config_does_not_fall_back_to_enabled_example(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            example = root / "config.example.yaml"
            example.write_text("enabled: true\nmode: shadow\n", encoding="utf-8")
            with (
                patch.object(config_module, "CONFIG_PATH", root / "missing.yaml"),
                patch.object(config_module, "EXAMPLE_PATH", example),
            ):
                cfg = load_config()
        self.assertFalse(cfg["enabled"])
        self.assertEqual("shadow", cfg["mode"])

    def test_example_config_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(config_module, "CONFIG_PATH", Path(tmp) / "missing.yaml"),
                patch.object(config_module, "EXAMPLE_PATH", Path(__file__).parents[1] / "config.example.yaml"),
            ):
                cfg = load_config()
        self.assertFalse(cfg["enabled"])
        self.assertEqual("shadow", cfg["mode"])
        self.assertFalse(yaml.safe_load((Path(__file__).parents[1] / "config.example.yaml").read_text(encoding="utf-8"))["enabled"])

    def test_invalid_transport_settings_disable_config(self) -> None:
        cases = (
            {"timeout": 0},
            {"timeout": 31.0},
            {"max_retries": 2},
            {"max_retries": "1"},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                with tempfile.TemporaryDirectory() as tmp:
                    config_path = Path(tmp) / "config.yaml"
                    lines = ["enabled: true", "mode: shadow"]
                    lines.extend(f"{key}: {value!r}" for key, value in overrides.items())
                    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    with patch.object(config_module, "CONFIG_PATH", config_path):
                        cfg = load_config()
                self.assertFalse(cfg["enabled"])
                self.assertEqual("invalid_transport_settings", cfg["config_error"])

    def test_invalid_policy_values_disable_config(self) -> None:
        cases = (
            ("thresholds", "min_choice_confidence", ".nan", "invalid_thresholds"),
            ("thresholds", "reuse_min", "1.1", "invalid_thresholds"),
            ("limits", "max_browser_sources", "-1", "invalid_limits"),
            ("limits", "max_retries_same_error", "0", "invalid_limits"),
            ("policy", "act_min", "0.8", "invalid_policy"),
        )
        for section, key, value, expected_error in cases:
            with self.subTest(section=section, key=key, value=value):
                with tempfile.TemporaryDirectory() as tmp:
                    config_path = Path(tmp) / "config.yaml"
                    config_path.write_text(
                        f"enabled: true\nmode: shadow\n{section}:\n  {key}: {value}\n",
                        encoding="utf-8",
                    )
                    with patch.object(config_module, "CONFIG_PATH", config_path):
                        cfg = load_config()
                self.assertFalse(cfg["enabled"])
                self.assertEqual(expected_error, cfg["config_error"])

    def test_log_path_outside_project_disables_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.yaml"
            config_path.write_text(
                "enabled: true\nmode: shadow\nlogging:\n  path: /tmp/outside.jsonl\n",
                encoding="utf-8",
            )
            with patch.object(config_module, "CONFIG_PATH", config_path):
                cfg = load_config()
        self.assertFalse(cfg["enabled"])
        self.assertEqual("invalid_logging_path", cfg["config_error"])

    def test_log_path_to_source_file_disables_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.yaml"
            config_path.write_text(
                "enabled: true\nmode: shadow\nlogging:\n  path: README.md\n",
                encoding="utf-8",
            )
            with patch.object(config_module, "CONFIG_PATH", config_path):
                cfg = load_config()
        self.assertFalse(cfg["enabled"])
        self.assertEqual("invalid_logging_path", cfg["config_error"])

    def test_symlinked_logs_directory_outside_project_disables_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            outside = root / "outside"
            project.mkdir()
            outside.mkdir()
            (project / "logs").symlink_to(outside, target_is_directory=True)
            config_path = project / "config.yaml"
            config_path.write_text(
                "enabled: true\nmode: shadow\nlogging:\n  path: logs/runs.jsonl\n",
                encoding="utf-8",
            )
            with (
                patch.object(config_module, "ROOT", project),
                patch.object(config_module, "CONFIG_PATH", config_path),
            ):
                cfg = load_config()
        self.assertFalse(cfg["enabled"])
        self.assertEqual("invalid_logging_path", cfg["config_error"])

    def test_duplicate_top_level_config_key_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.yaml"
            config_path.write_text(
                "enabled: false\nenabled: true\nmode: shadow\n",
                encoding="utf-8",
            )
            with patch.object(config_module, "CONFIG_PATH", config_path):
                cfg = load_config()
        self.assertFalse(cfg["enabled"])
        self.assertEqual("invalid_yaml", cfg["config_error"])

    def test_duplicate_nested_config_key_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.yaml"
            config_path.write_text(
                "enabled: true\nmode: shadow\nlogging:\n"
                "  path: logs/one.jsonl\n  path: /tmp/outside.jsonl\n",
                encoding="utf-8",
            )
            with patch.object(config_module, "CONFIG_PATH", config_path):
                cfg = load_config()
        self.assertFalse(cfg["enabled"])
        self.assertEqual("invalid_yaml", cfg["config_error"])

    def test_corrupt_local_config_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.yaml"
            config_path.write_text("enabled: [\n", encoding="utf-8")
            with patch.object(config_module, "CONFIG_PATH", config_path):
                cfg = load_config()
        self.assertFalse(cfg["enabled"])
        self.assertEqual("shadow", cfg["mode"])


class RouterSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.log_path = Path(self.tmp.name) / "runs.jsonl"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_account_reuse_cache_signal_keeps_human_tripwire(self) -> None:
        result = result_stub()
        result.choices["intent"].choice = "account"
        result.nouls["reuse_cache"].noul = 0.9
        with (
            patch.object(router_module, "load_config", return_value=enabled_config()),
            patch.object(router_module, "resolve_log_path", return_value=self.log_path),
            patch("src.jev_client.system_one", return_value=result),
        ):
            out = router_module.route_task(
                {
                    "goal": "send email now",
                    "kind": "account",
                    "cached_artifact": True,
                }
            )
        self.assertEqual("ask_human", out["action"])
        self.assertTrue(out["jev_used"])

    def test_account_retry_signal_keeps_human_tripwire(self) -> None:
        result = result_stub()
        result.choices["intent"].choice = "account"
        result.nouls["stop_retry"].noul = 0.9
        with (
            patch.object(router_module, "load_config", return_value=enabled_config()),
            patch.object(router_module, "resolve_log_path", return_value=self.log_path),
            patch("src.jev_client.system_one", return_value=result),
        ):
            out = router_module.route_task(
                {
                    "goal": "send email now",
                    "kind": "account",
                    "same_error_count": 2,
                }
            )
        self.assertEqual("ask_human", out["action"])
        self.assertTrue(out["jev_used"])

    def test_documented_cache_field_keeps_human_tripwire(self) -> None:
        result = result_stub()
        result.choices["intent"].choice = "account"
        result.nouls["reuse_cache"].noul = 0.9
        with (
            patch.object(router_module, "load_config", return_value=enabled_config()),
            patch.object(router_module, "resolve_log_path", return_value=self.log_path),
            patch("src.jev_client.system_one", return_value=result),
        ):
            out = router_module.route_task(
                {
                    "goal": "send email now",
                    "kind": "account",
                    "has_cached_artifact": True,
                }
            )
        self.assertEqual("ask_human", out["action"])
        self.assertTrue(out["jev_used"])

    def test_documented_cache_field_enables_reuse(self) -> None:
        result = result_stub()
        result.nouls["reuse_cache"].noul = 0.9
        with (
            patch.object(router_module, "load_config", return_value=enabled_config()),
            patch.object(router_module, "resolve_log_path", return_value=self.log_path),
            patch("src.jev_client.system_one", return_value=result),
        ):
            out = router_module.route_task(
                {
                    "goal": "use the fresh briefing",
                    "kind": "research",
                    "has_cached_artifact": True,
                }
            )
        self.assertEqual("reuse_cache", out["action"])
        self.assertTrue(out["jev_used"])

    def test_documented_cache_field_takes_precedence_over_legacy_alias(self) -> None:
        result = result_stub()
        result.nouls["reuse_cache"].noul = 0.9
        with (
            patch.object(router_module, "load_config", return_value=enabled_config()),
            patch.object(router_module, "resolve_log_path", return_value=self.log_path),
            patch("src.jev_client.system_one", return_value=result),
        ):
            out = router_module.route_task(
                {
                    "goal": "fresh field overrides legacy alias",
                    "kind": "research",
                    "has_cached_artifact": False,
                    "cached_artifact": True,
                }
            )
        self.assertEqual("research_capped", out["action"])

    def test_non_boolean_cache_field_returns_conservative_route(self) -> None:
        result = result_stub()
        result.nouls["reuse_cache"].noul = 0.9
        with (
            patch.object(router_module, "load_config", return_value=enabled_config()),
            patch.object(router_module, "resolve_log_path", return_value=self.log_path),
            patch("src.jev_client.system_one", return_value=result),
        ):
            out = router_module.route_task(
                {
                    "goal": "invalid cache flag",
                    "kind": "research",
                    "has_cached_artifact": "false",
                }
            )
        self.assertEqual("proceed_full", out["action"])
        self.assertFalse(out["jev_used"])
        self.assertEqual("ValueError", out["details"]["error_class"])

    def test_documented_message_field_triggers_bypass(self) -> None:
        with (
            patch.object(router_module, "load_config", return_value=enabled_config()),
            patch.object(router_module, "resolve_log_path", return_value=self.log_path),
            patch("src.jev_client.system_one") as call,
        ):
            out = router_module.route_task(
                {"goal": "message alias case", "message": "please bypass jev now"}
            )
        self.assertEqual("proceed_full", out["action"])
        self.assertFalse(out["jev_used"])
        call.assert_not_called()

    def test_cli_rejects_invalid_json_without_traceback(self) -> None:
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            exit_code = cli_main(["not-json"])
        self.assertEqual(2, exit_code)
        self.assertIn("invalid JSON state", errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())

    def test_cli_returns_conservative_route_when_router_raises(self) -> None:
        captured = io.StringIO()
        errors = io.StringIO()
        with (
            patch("src.cli.route_task", side_effect=RuntimeError("sensitive router detail")),
            contextlib.redirect_stdout(captured),
            contextlib.redirect_stderr(errors),
        ):
            exit_code = cli_main(['{"goal":"CLI fallback case","kind":"research"}'])
        self.assertEqual(0, exit_code)
        output = json.loads(captured.getvalue())
        self.assertEqual("proceed_full", output["action"])
        self.assertFalse(output["jev_used"])
        self.assertNotIn("sensitive router detail", captured.getvalue())
        self.assertNotIn("sensitive router detail", errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())

    def test_cli_wires_explicit_native_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "runs.jsonl"
            captured = io.StringIO()
            with (
                patch.object(router_module, "load_config", return_value=enabled_config()),
                patch.object(router_module, "resolve_log_path", return_value=log_path),
                patch("src.jev_client.system_one", return_value=result_stub()) as call,
                contextlib.redirect_stdout(captured),
            ):
                exit_code = cli_main(
                    ['{"goal": "native wiring test", "kind": "research"}']
                )
        self.assertEqual(0, exit_code)
        output = json.loads(captured.getvalue())
        self.assertTrue(output["jev_used"])
        self.assertEqual("research_capped", output["action"])
        call.assert_called_once()
        kwargs = call.call_args.kwargs
        self.assertEqual("experientiallabs_native", kwargs["provider"])
        self.assertEqual("https://api.experientiallabs.ai", kwargs["base_url"])
        self.assertEqual("HERMES_CUSTOM_API_EXPERIENTIALLABS_AI_API_KEY", kwargs["credential_env"])
        self.assertNotIn("TYPESAFE_API_KEY", kwargs["credential_env"])

    def test_config_loader_failure_returns_conservative_route(self) -> None:
        with (
            patch.object(router_module, "load_config", side_effect=OSError("loader unavailable")),
            patch.object(router_module, "resolve_log_path", return_value=self.log_path),
            patch("src.jev_client.system_one") as call,
        ):
            out = router_module.route_task({"goal": "loader failure case", "kind": "research"})
        self.assertEqual("proceed_full", out["action"])
        self.assertFalse(out["jev_used"])
        self.assertEqual("OSError", out["details"]["error_class"])
        call.assert_not_called()
        record = json.loads(self.log_path.read_text(encoding="utf-8"))
        self.assertEqual(
            hashlib.sha256(b"loader failure case").hexdigest(), record["goal_sha256"]
        )

    def test_unwritable_audit_path_skips_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "not-a-directory"
            blocker.write_text("occupied", encoding="utf-8")
            log_path = blocker / "runs.jsonl"
            with (
                patch.object(router_module, "load_config", return_value=enabled_config()),
                patch.object(router_module, "resolve_log_path", return_value=log_path),
                patch("src.jev_client.system_one") as call,
            ):
                out = router_module.route_task({"goal": "audit failure case", "kind": "research"})
        self.assertEqual("proceed_full", out["action"])
        self.assertFalse(out["jev_used"])
        call.assert_not_called()

    def test_post_provider_audit_failure_disables_enforcement(self) -> None:
        cfg = enabled_config()
        cfg["mode"] = "active"
        with (
            patch.object(router_module, "load_config", return_value=cfg),
            patch.object(router_module, "resolve_log_path", return_value=self.log_path),
            patch("src.jev_client.system_one", return_value=result_stub()) as call,
            patch.object(
                router_module,
                "log_run",
                side_effect=OSError("append failed after preflight"),
            ),
        ):
            out = router_module.route_task(
                {"goal": "audit append failure case", "kind": "research"}
            )
        call.assert_called_once()
        self.assertEqual("proceed_full", out["action"])
        self.assertEqual("shadow", out["mode"])
        self.assertTrue(out["jev_used"])
        self.assertFalse(out["policy"]["honor_in_active_mode"])
        self.assertTrue(out["policy"]["shadow_mode_is_advisory"])

    def test_provider_error_returns_conservative_route(self) -> None:
        with (
            patch.object(router_module, "load_config", return_value=enabled_config()),
            patch.object(router_module, "resolve_log_path", return_value=self.log_path),
            patch("src.jev_client.system_one", side_effect=TypeSafeError("test transport failure")) as call,
        ):
            out = router_module.route_task({"goal": "sanitized goal", "kind": "research"})
        self.assertEqual("proceed_full", out["action"])
        self.assertFalse(out["jev_used"])
        self.assertEqual("TypeSafeError", out["details"]["error_class"])
        call.assert_called_once()

    def test_provider_failure_is_advisory_even_if_config_is_active(self) -> None:
        cfg = enabled_config()
        cfg["mode"] = "active"
        with (
            patch.object(router_module, "load_config", return_value=cfg),
            patch.object(router_module, "resolve_log_path", return_value=self.log_path),
            patch("src.jev_client.system_one", side_effect=TypeSafeError("provider failed")),
        ):
            out = router_module.route_task({"goal": "active fallback case", "kind": "research"})
        self.assertEqual("proceed_full", out["action"])
        self.assertFalse(out["jev_used"])
        self.assertEqual("shadow", out["mode"])
        self.assertFalse(out["policy"]["honor_in_active_mode"])
        self.assertTrue(out["policy"]["shadow_mode_is_advisory"])

    def test_failure_audit_record_is_bounded_metadata_only(self) -> None:
        with (
            patch.object(router_module, "load_config", return_value=enabled_config()),
            patch.object(router_module, "resolve_log_path", return_value=self.log_path),
            patch("src.jev_client.system_one", side_effect=TypeSafeError("sensitive transport detail")),
        ):
            router_module.route_task({"goal": "sensitive failure goal", "kind": "research"})
        record = json.loads(self.log_path.read_text(encoding="utf-8"))
        self.assertEqual(
            {
                "event",
                "ts",
                "goal_sha256",
                "action",
                "mode",
                "jev_used",
                "error_class",
            },
            set(record),
        )
        self.assertNotIn("reason", record)
        self.assertNotIn("details", record)
        persisted = self.log_path.read_text(encoding="utf-8")
        self.assertNotIn("sensitive failure goal", persisted)
        self.assertNotIn("sensitive transport detail", persisted)

    def test_missing_answer_key_returns_conservative_route(self) -> None:
        with (
            patch.object(router_module, "load_config", return_value=enabled_config()),
            patch.object(router_module, "resolve_log_path", return_value=self.log_path),
            patch("src.jev_client.system_one", return_value=result_stub(include_intent=False)),
        ):
            out = router_module.route_task({"goal": "sanitized goal", "kind": "research"})
        self.assertEqual("proceed_full", out["action"])
        self.assertFalse(out["jev_used"])
        self.assertEqual("KeyError", out["details"]["error_class"])

    def test_out_of_range_provider_values_return_conservative_route(self) -> None:
        cases = (
            ("choice_confidence", lambda result: setattr(result.choices["intent"], "confidence", 1.1)),
            ("choice_probability", lambda result: result.choices["intent"].probabilities.update({"research": -0.1})),
            ("choice_probability_string", lambda result: result.choices["intent"].probabilities.update({"research": "0.5"})),
            ("choice_confidence_bool", lambda result: setattr(result.choices["intent"], "confidence", True)),
            ("noul", lambda result: setattr(result.nouls["reuse_cache"], "noul", 2.0)),
            ("complexity", lambda result: setattr(result.scores["complexity"], "score", 2.1)),
            ("intent_membership", lambda result: setattr(result.choices["intent"], "choice", "unknown")),
        )
        for name, mutate in cases:
            with self.subTest(name=name):
                result = result_stub()
                mutate(result)
                with (
                    patch.object(router_module, "load_config", return_value=enabled_config()),
                    patch.object(router_module, "resolve_log_path", return_value=self.log_path),
                    patch("src.jev_client.system_one", return_value=result),
                ):
                    out = router_module.route_task(
                        {"goal": f"invalid {name}", "kind": "research"}
                    )
                self.assertEqual("proceed_full", out["action"])
                self.assertFalse(out["jev_used"])
                self.assertEqual("ValueError", out["details"]["error_class"])

    def test_direct_client_import_failure_returns_conservative_route(self) -> None:
        original_import = builtins.__import__

        def fail_client_import(name, *args, **kwargs):
            if name == "src.jev_client":
                raise ModuleNotFoundError("missing client")
            return original_import(name, *args, **kwargs)

        with (
            patch.object(router_module, "load_config", return_value=enabled_config()),
            patch.object(router_module, "resolve_log_path", return_value=self.log_path),
            patch("builtins.__import__", side_effect=fail_client_import),
        ):
            out = router_module.route_task({"goal": "import failure case", "kind": "research"})
        self.assertEqual("proceed_full", out["action"])
        self.assertFalse(out["jev_used"])
        self.assertEqual("ModuleNotFoundError", out["details"]["error_class"])

    def test_launcher_works_outside_repository(self) -> None:
        root = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [str(root / "bin" / "jev-route"), "not-json"],
                cwd=tmp,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
        self.assertEqual(2, completed.returncode, completed.stderr)
        self.assertIn("invalid JSON state", completed.stderr)

    def test_non_finite_provider_values_return_conservative_route(self) -> None:
        result = result_stub()
        result.choices["intent"].confidence = float("nan")
        result.nouls["reuse_cache"].noul = float("inf")
        with (
            patch.object(router_module, "load_config", return_value=enabled_config()),
            patch.object(router_module, "resolve_log_path", return_value=self.log_path),
            patch("src.jev_client.system_one", return_value=result),
        ):
            out = router_module.route_task(
                {"goal": "non-finite provider case", "kind": "research"}
            )
        self.assertEqual("proceed_full", out["action"])
        self.assertFalse(out["jev_used"])
        self.assertEqual("shadow", out["mode"])
        self.assertEqual("ValueError", out["details"]["error_class"])
        record = json.loads(self.log_path.read_text(encoding="utf-8"))
        self.assertEqual("ValueError", record["error_class"])

    def test_enabled_route_logs_goal_hash_and_no_raw_state(self) -> None:
        state = {
            "goal": "sensitive goal text",
            "kind": "research",
            "cached_artifact": True,
            "cached_note": "sensitive cached note",
            "prior_error": "sensitive prior error",
            "same_error_count": 2,
            "constraints": "sensitive constraints",
        }
        with (
            patch.object(router_module, "load_config", return_value=enabled_config()),
            patch.object(router_module, "resolve_log_path", return_value=self.log_path),
            patch("src.jev_client.system_one", return_value=result_stub()),
        ):
            out = router_module.route_task(state)
        self.assertTrue(out["jev_used"])
        record = json.loads(self.log_path.read_text(encoding="utf-8"))
        expected_hash = hashlib.sha256(state["goal"].encode("utf-8")).hexdigest()
        self.assertEqual(expected_hash, record["goal_sha256"])
        self.assertEqual("experientiallabs_native", record["provider"])
        self.assertEqual("jev-latest", record["model"])
        self.assertTrue(record["jev_used"])
        self.assertEqual(
            {"choice_count": 1, "noul_count": 3, "score_count": 1},
            record["primitive_counts"],
        )
        self.assertNotIn("details", record)
        self.assertNotIn("reason", record)
        persisted = self.log_path.read_text(encoding="utf-8")
        for raw in (
            state["goal"],
            state["cached_note"],
            state["prior_error"],
            state["constraints"],
        ):
            self.assertNotIn(raw, persisted)

    def test_disabled_route_logs_goal_hash_and_no_raw_state(self) -> None:
        cfg = enabled_config()
        cfg["enabled"] = False
        state = {"goal": "disabled sensitive goal", "kind": "research"}
        with (
            patch.object(router_module, "load_config", return_value=cfg),
            patch.object(router_module, "resolve_log_path", return_value=self.log_path),
        ):
            out = router_module.route_task(state)
        self.assertFalse(out["jev_used"])
        record = json.loads(self.log_path.read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256(state["goal"].encode("utf-8")).hexdigest(), record["goal_sha256"])
        self.assertNotIn(state["goal"], self.log_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
