from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yaml"
EXAMPLE_PATH = ROOT / "config.example.yaml"

MIN_TIMEOUT = 0.1
MAX_TIMEOUT = 30.0
MAX_RETRIES = 1
ALLOWED_PROVIDERS = {"typesafe_official", "experientiallabs_native"}


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys at every depth."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader, node: MappingNode, deep: bool = False
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key: {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def _defaults() -> dict[str, Any]:
    return {
        "enabled": False,
        "mode": "shadow",
        "model": "jev-latest",
        "provider": "typesafe_official",
        "base_url": "https://api.typesafe.ai",
        "credential_env": "TYPESAFE_API_KEY",
        "timeout": 5.0,
        "max_retries": 1,
        "thresholds": {},
        "limits": {"max_browser_sources": 5, "max_retries_same_error": 1},
        "logging": {"path": "logs/runs.jsonl"},
    }


def _valid_timeout(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and MIN_TIMEOUT <= float(value) <= MAX_TIMEOUT
    )


def _valid_max_retries(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= MAX_RETRIES


def _valid_probability(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    )


def _valid_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _valid_log_path(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    path = Path(value)
    if path.is_absolute():
        return False
    try:
        root = ROOT.resolve()
        logs = (root / "logs").resolve()
        logs.relative_to(root)
        resolved = (root / path).resolve()
        resolved.relative_to(logs)
    except (OSError, RuntimeError, ValueError):
        return False
    return resolved != logs and resolved.suffix == ".jsonl"


def _validate_config(data: dict[str, Any]) -> None:
    errors: list[str] = []

    if not isinstance(data.get("enabled"), bool):
        errors.append("invalid_enabled")
    if data.get("mode") not in {"shadow", "active"}:
        errors.append("invalid_mode")
        data["mode"] = "shadow"
    if not isinstance(data.get("model"), str) or not data["model"].strip():
        errors.append("invalid_model")
    if data.get("provider") not in ALLOWED_PROVIDERS:
        errors.append("invalid_provider")
    if not isinstance(data.get("base_url"), str) or not data["base_url"].strip():
        errors.append("invalid_base_url")
    if not isinstance(data.get("credential_env"), str) or not data["credential_env"].strip():
        errors.append("invalid_credential_env")

    if not _valid_timeout(data.get("timeout")):
        errors.append("invalid_transport_settings")
    if not _valid_max_retries(data.get("max_retries")):
        errors.append("invalid_transport_settings")

    for key in ("thresholds", "limits"):
        if not isinstance(data.get(key), dict):
            errors.append(f"invalid_{key}")

    if "policy" in data:
        errors.append("invalid_policy")

    thresholds = data.get("thresholds")
    if isinstance(thresholds, dict) and not all(
        _valid_probability(value)
        for value in (
            thresholds.get("min_choice_confidence", 0.55),
            thresholds.get("reuse_min", 0.65),
            thresholds.get("subagent_min", 0.75),
            thresholds.get("stop_retry_min", 0.55),
        )
    ):
        errors.append("invalid_thresholds")

    limits = data.get("limits")
    if isinstance(limits, dict) and not all(
        _valid_positive_int(value)
        for value in (
            limits.get("max_browser_sources", 5),
            limits.get("max_retries_same_error", 1),
        )
    ):
        errors.append("invalid_limits")

    logging_data = data.get("logging")
    if not isinstance(logging_data, dict):
        errors.append("invalid_logging")
    elif not _valid_log_path(logging_data.get("path", "logs/runs.jsonl")):
        errors.append("invalid_logging_path")
        data["logging"] = {"path": "logs/runs.jsonl"}

    if errors:
        data["config_error"] = errors[0]
        data["enabled"] = False
    else:
        data["enabled"] = data.get("enabled") is True


def load_config() -> dict[str, Any]:
    """Load only the ignored local config; missing or invalid config stays disabled."""
    data = _defaults()
    try:
        path_exists = CONFIG_PATH.exists()
    except OSError:
        data["config_error"] = "config_unreadable"
        data["enabled"] = False
        return data

    if path_exists:
        try:
            loaded = yaml.load(CONFIG_PATH.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
        except (OSError, yaml.YAMLError):
            data["config_error"] = "invalid_yaml"
            data["enabled"] = False
            return data
        if not isinstance(loaded, dict):
            data["config_error"] = "invalid_config_type"
            data["enabled"] = False
            return data
        for key in ("thresholds", "limits", "logging"):
            if key in loaded:
                if not isinstance(loaded[key], dict):
                    data[key] = loaded[key]
                else:
                    data[key].update(loaded[key])
        data.update({k: v for k, v in loaded.items() if k not in {"thresholds", "limits", "logging"}})

    _validate_config(data)
    return data


def resolve_log_path(cfg: dict[str, Any]) -> Path:
    """Resolve a project-local log path, rejecting absolute paths and traversal."""
    logging_data = cfg.get("logging")
    if not isinstance(logging_data, dict):
        raise ValueError("invalid logging configuration")
    rel = logging_data.get("path", "logs/runs.jsonl")
    if not isinstance(rel, str) or not rel.strip():
        raise ValueError("invalid logging path")
    path = Path(rel)
    if not _valid_log_path(rel):
        raise ValueError("logging path must be a .jsonl file under the project logs directory")
    resolved = (ROOT / path).resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved
