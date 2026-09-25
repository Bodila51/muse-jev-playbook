from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Mapping
from typing import Any

from src.config import load_config, resolve_log_path
from src.logger import log_run


BYPASS_MARKERS = ("bypass jev", "no jev")


def _bypassed(state: dict[str, Any]) -> bool:
    raw = " ".join(
        str(state.get(k, ""))
        for k in ("goal", "raw", "user_message", "message", "notes")
    ).lower()
    return any(m in raw for m in BYPASS_MARKERS)


INTENT_CRITERIA = {
    "chat": "Short answer or conversation; no tools needed",
    "lookup": "Known file/API/status check; mostly deterministic",
    "research": "Needs web/search and synthesis",
    "browser": "Needs interactive browser clicks",
    "coding": "Edit code / tests / repo work",
    "write": "Draft long prose, email, or document",
    "account": "Send, publish, pay, delete, change permissions",
}


def build_questions() -> dict[str, Any]:
    """Default question pack. Import lazily so the kill-switch path stays dependency-free."""
    from typesafe_sdk import Choice, Noul, Score

    return {
        "intent": Choice(
            instructions="What kind of work does this request mainly need?",
            criteria=INTENT_CRITERIA,
        ),
        "reuse_cache": Noul(
            instructions="Is there already a fresh enough cached result that should be reused instead of doing new heavy work?"
        ),
        "needs_subagent": Noul(
            instructions="Does this clearly need an extra specialized subagent (research/browser/coding) beyond one agent turn?"
        ),
        "stop_retry": Noul(
            instructions="Given prior_error and same_error_count, should we STOP retrying the same approach?"
        ),
        "complexity": Score(
            instructions="How much agent effort is justified?",
            criteria=[
                "Trivial — one step or cached",
                "Normal — short tool use",
                "Heavy — multi-step research/browser/coding",
            ],
        ),
    }


def normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    has_cached_artifact = (
        state["has_cached_artifact"]
        if "has_cached_artifact" in state
        else state.get("cached_artifact", False)
    )
    if not isinstance(has_cached_artifact, bool):
        raise ValueError("cache artifact flag must be boolean")
    return {
        "goal": state.get("goal") or state.get("raw") or "",
        "kind_hint": state.get("kind") or state.get("kind_hint") or "unknown",
        "has_cached_artifact": has_cached_artifact,
        "cached_note": state.get("cached_note") or "",
        "prior_error": state.get("prior_error") or "",
        "same_error_count": int(state.get("same_error_count") or 0),
        "sources_found": int(state.get("sources_found") or 0),
        "constraints": state.get("constraints") or "",
    }


def _finite_number(value: Any) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("provider value must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite provider value")
    return number


def _bounded_number(value: Any, minimum: float, maximum: float) -> float:
    number = _finite_number(value)
    if not minimum <= number <= maximum:
        raise ValueError("provider value out of range")
    return number


def decide_action(jstate: dict[str, Any], result: Any, cfg: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """Map Jev outputs to an action via configured thresholds. Pure function (testable offline)."""
    thr = cfg.get("thresholds") or {}
    limits = cfg.get("limits") or {}

    intent = result.choices["intent"]
    reuse = result.nouls["reuse_cache"]
    sub = result.nouls["needs_subagent"]
    stop = result.nouls["stop_retry"]
    complexity = result.scores["complexity"]

    reuse_n = _bounded_number(reuse.noul, 0.0, 1.0)
    sub_n = _bounded_number(sub.noul, 0.0, 1.0)
    stop_n = _bounded_number(stop.noul, 0.0, 1.0)
    raw_complexity = _bounded_number(complexity.score, 0.0, 2.0)
    comp = raw_complexity / 2.0  # score 0..2 -> 0..1
    min_conf = _bounded_number(thr.get("min_choice_confidence", 0.55), 0.0, 1.0)
    intent_conf = _bounded_number(intent.confidence, 0.0, 1.0)
    intent_probs = {
        k: round(_bounded_number(v, 0.0, 1.0), 4)
        for k, v in (intent.probabilities or {}).items()
    }
    if intent.choice not in INTENT_CRITERIA:
        raise ValueError("provider intent outside known choices")

    action = "proceed_full"
    reason = "default full agent work"

    if intent.choice == "account":
        action = "ask_human"
        reason = "account/irreversible class - require approval"
    elif jstate["has_cached_artifact"] and reuse_n >= _bounded_number(thr.get("reuse_min", 0.65), 0.0, 1.0):
        action = "reuse_cache"
        reason = f"reuse_cache noul={reuse_n:.2f}"
    elif jstate["same_error_count"] >= int(limits.get("max_retries_same_error", 1)) \
            and stop_n >= _bounded_number(thr.get("stop_retry_min", 0.55), 0.0, 1.0):
        action = "stop_retry"
        reason = f"stop_retry noul={stop_n:.2f} same_error_count={jstate['same_error_count']}"
    elif intent.choice == "lookup" and intent_conf >= min_conf:
        action = "run_deterministic"
        reason = "intent=lookup"
    elif intent.choice == "chat" and intent_conf >= min_conf:
        action = "chat_only"
        reason = "intent=chat"
    elif sub_n >= _bounded_number(thr.get("subagent_min", 0.75), 0.0, 1.0):
        action = "allow_subagent"
        reason = f"needs_subagent noul={sub_n:.2f}"
    elif (
        intent.choice in {"research", "browser"}
        and intent_conf >= min_conf
    ):
        action = "research_capped"
        reason = f"cap sources at {limits.get('max_browser_sources', 5)}"

    details = {
        "intent": intent.choice,
        "intent_confidence": round(intent_conf, 4),
        "intent_probs": intent_probs,
        "reuse_cache": round(reuse_n, 4),
        "needs_subagent": round(sub_n, 4),
        "stop_retry": round(stop_n, 4),
        "complexity_0_1": round(comp, 4),
        "max_browser_sources": int(limits.get("max_browser_sources", 5)),
    }
    return action, reason, details


def _goal_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _primitive_counts(result: Any) -> dict[str, int]:
    """Return only bounded primitive cardinalities; never retain answer contents."""
    counts = {"choice_count": 0, "noul_count": 0, "score_count": 0}
    for name, key in (("choices", "choice_count"), ("nouls", "noul_count"), ("scores", "score_count")):
        collection = getattr(result, name, None)
        if isinstance(collection, Mapping):
            counts[key] = len(collection)
    return counts


def _safe_error_class(exc: BaseException) -> str:
    return type(exc).__name__


def _bounded_audit_record(*, goal_sha256: str, out: Mapping[str, Any]) -> dict[str, Any]:
    """Build the persisted allowlist; never serialize route diagnostics or payload data."""
    record: dict[str, Any] = {
        "event": "route",
        "goal_sha256": goal_sha256,
        "action": out.get("action", "proceed_full"),
        "mode": out.get("mode", "shadow"),
        "jev_used": bool(out.get("jev_used", False)),
    }
    details = out.get("details")
    if isinstance(details, Mapping) and isinstance(details.get("error_class"), str):
        record["error_class"] = details["error_class"]
    return record


def _fallback_config() -> dict[str, Any]:
    """Return the smallest safe configuration when the loader itself fails."""
    return {
        "enabled": False,
        "mode": "shadow",
        "logging": {"path": "logs/runs.jsonl"},
    }


def _state_goal_for_log(state: object) -> str:
    """Extract a bounded string goal without allowing malformed state to escape."""
    if not isinstance(state, dict):
        return ""
    try:
        value = state.get("goal") or state.get("raw") or ""
        return str(value)
    except Exception:
        return ""


def _conservative_route(cfg: dict[str, Any], *, reason: str, error_class: str | None = None) -> dict[str, Any]:
    details: dict[str, Any] = {}
    if error_class:
        details["error_class"] = error_class
    return {
        "action": "proceed_full",
        "reason": reason,
        "mode": "shadow",
        "jev_used": False,
        "details": details,
        "policy": {
            "honor_in_active_mode": False,
            "shadow_mode_is_advisory": True,
        },
    }


def _safe_log(log_path: Any, record: dict[str, Any]) -> bool:
    """Persist bounded metadata and report whether the append succeeded."""
    if log_path is None:
        return False
    try:
        log_run(log_path, record)
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Jev audit log unavailable: %s", type(exc).__name__
        )
        return False
    return True


def _audit_ready(log_path: Any) -> bool:
    """Check that the selected audit file can be appended before a provider call."""
    if log_path is None:
        return False
    try:
        with open(log_path, "a", encoding="utf-8"):
            pass
    except (OSError, TypeError, ValueError):
        return False
    return True


def route_task(state: dict[str, Any]) -> dict[str, Any]:
    """Run Jev gates and return a routing decision for the agent."""
    try:
        cfg = load_config()
    except Exception as exc:
        cfg = _fallback_config()
        try:
            log_path = resolve_log_path(cfg)
        except Exception:
            log_path = None
        out = _conservative_route(
            cfg, reason="Jev configuration failure", error_class=type(exc).__name__
        )
        _safe_log(
            log_path,
            _bounded_audit_record(
                goal_sha256=_goal_hash(_state_goal_for_log(state)), out=out
            ),
        )
        return out
    try:
        log_path = resolve_log_path(cfg)
    except Exception as exc:
        return _conservative_route(
            cfg, reason="Jev configuration failure", error_class=type(exc).__name__
        )

    if not isinstance(state, dict):
        out = _conservative_route(
            cfg, reason="Jev input failure", error_class="TypeError"
        )
        _safe_log(log_path, _bounded_audit_record(goal_sha256="", out=out))
        return out

    goal = state.get("goal") or state.get("raw") or ""
    goal_sha256 = _goal_hash(goal)

    if not cfg.get("enabled", False) or _bypassed(state):
        out = _conservative_route(cfg, reason="disabled or bypass jev")
        _safe_log(log_path, _bounded_audit_record(goal_sha256=goal_sha256, out=out))
        return out

    if not _audit_ready(log_path):
        return _conservative_route(
            cfg, reason="Jev audit unavailable", error_class="OSError"
        )

    try:
        # Lazy import: the kill-switch path above stays dependency-free.
        from src.jev_client import system_one

        model = cfg.get("model") or "jev-latest"
        jstate = normalize_state(state)
        result = system_one(
            jstate,
            build_questions(),
            model=model,
            provider=cfg.get("provider", "typesafe_official"),
            base_url=cfg.get("base_url"),
            credential_env=cfg.get("credential_env"),
            timeout=cfg.get("timeout", 5.0),
            max_retries=cfg.get("max_retries", 1),
        )
        action, reason, details = decide_action(jstate, result, cfg)
    except Exception as exc:
        out = _conservative_route(
            cfg, reason="Jev provider or policy failure", error_class=_safe_error_class(exc)
        )
        _safe_log(log_path, _bounded_audit_record(goal_sha256=goal_sha256, out=out))
        return out

    out = {
        "action": action,
        "reason": reason,
        "mode": cfg.get("mode"),
        "jev_used": True,
        "details": details,
        "policy": {
            "honor_in_active_mode": True,
            "shadow_mode_is_advisory": cfg.get("mode") == "shadow",
        },
    }
    if not _safe_log(
        log_path,
        {
            "event": "route",
            "goal_sha256": goal_sha256,
            "provider": cfg.get("provider"),
            "model": model,
            "action": action,
            "mode": cfg.get("mode"),
            "primitive_counts": _primitive_counts(result),
            "jev_used": True,
        },
    ):
        return {
            "action": "proceed_full",
            "reason": "Jev audit unavailable after provider call",
            "mode": "shadow",
            "jev_used": True,
            "details": {"error_class": "OSError"},
            "policy": {
                "honor_in_active_mode": False,
                "shadow_mode_is_advisory": True,
            },
        }
    return out
