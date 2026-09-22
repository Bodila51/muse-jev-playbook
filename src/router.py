from __future__ import annotations

from typing import Any

from src.config import load_config, resolve_log_path
from src.logger import log_run


BYPASS_MARKERS = ("bypass jev", "no jev")


def _bypassed(state: dict[str, Any]) -> bool:
    raw = " ".join(
        str(state.get(k, ""))
        for k in ("goal", "raw", "user_message", "notes")
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
    return {
        "goal": state.get("goal") or state.get("raw") or "",
        "kind_hint": state.get("kind") or state.get("kind_hint") or "unknown",
        "has_cached_artifact": bool(state.get("cached_artifact")),
        "cached_note": state.get("cached_note") or "",
        "prior_error": state.get("prior_error") or "",
        "same_error_count": int(state.get("same_error_count") or 0),
        "sources_found": int(state.get("sources_found") or 0),
        "constraints": state.get("constraints") or "",
    }


def decide_action(jstate: dict[str, Any], result: Any, cfg: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """Map Jev outputs to an action via configured thresholds. Pure function (testable offline)."""
    thr = cfg.get("thresholds") or {}
    limits = cfg.get("limits") or {}

    intent = result.choices["intent"]
    reuse = result.nouls["reuse_cache"]
    sub = result.nouls["needs_subagent"]
    stop = result.nouls["stop_retry"]
    complexity = result.scores["complexity"]

    reuse_n = float(reuse.noul)
    sub_n = float(sub.noul)
    stop_n = float(stop.noul)
    comp = float(complexity.score) / 2.0  # score 0..2 -> 0..1
    min_conf = float(thr.get("min_choice_confidence", 0.55))

    action = "proceed_full"
    reason = "default full agent work"

    if jstate["has_cached_artifact"] and reuse_n >= float(thr.get("reuse_min", 0.65)):
        action = "reuse_cache"
        reason = f"reuse_cache noul={reuse_n:.2f}"
    elif jstate["same_error_count"] >= int(limits.get("max_retries_same_error", 1)) \
            and stop_n >= float(thr.get("stop_retry_min", 0.55)):
        action = "stop_retry"
        reason = f"stop_retry noul={stop_n:.2f} same_error_count={jstate['same_error_count']}"
    elif intent.choice == "lookup" and float(intent.confidence) >= min_conf:
        action = "run_deterministic"
        reason = "intent=lookup"
    elif intent.choice == "chat" and float(intent.confidence) >= min_conf:
        action = "chat_only"
        reason = "intent=chat"
    elif intent.choice == "account":
        action = "ask_human"
        reason = "account/irreversible class - require approval"
    elif sub_n >= float(thr.get("subagent_min", 0.75)):
        action = "allow_subagent"
        reason = f"needs_subagent noul={sub_n:.2f}"
    elif intent.choice in {"research", "browser"}:
        action = "research_capped"
        reason = f"cap sources at {limits.get('max_browser_sources', 5)}"

    details = {
        "intent": intent.choice,
        "intent_confidence": round(float(intent.confidence), 4),
        "intent_probs": {k: round(float(v), 4) for k, v in (intent.probabilities or {}).items()},
        "reuse_cache": round(reuse_n, 4),
        "needs_subagent": round(sub_n, 4),
        "stop_retry": round(stop_n, 4),
        "complexity_0_1": round(comp, 4),
        "max_browser_sources": int(limits.get("max_browser_sources", 5)),
    }
    return action, reason, details


def route_task(state: dict[str, Any]) -> dict[str, Any]:
    """Run Jev gates and return a routing decision for the agent."""
    cfg = load_config()
    log_path = resolve_log_path(cfg)

    if not cfg.get("enabled", True) or _bypassed(state):
        out = {
            "action": "proceed_full",
            "reason": "disabled or bypass jev",
            "mode": cfg.get("mode"),
            "jev_used": False,
            "details": {},
        }
        log_run(log_path, {"event": "route", "state_goal": str(state.get("goal"))[:300], **out})
        return out

    model = cfg.get("model") or "jev-latest"
    jstate = normalize_state(state)
    # Lazy import: the kill-switch path above stays dependency-free.
    from src.jev_client import system_one

    result = system_one(jstate, build_questions(), model=model)
    action, reason, details = decide_action(jstate, result, cfg)

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
    log_run(
        log_path,
        {
            "event": "route",
            "goal": jstate["goal"][:300],
            "action": action,
            "reason": reason,
            "mode": cfg.get("mode"),
            "details": details,
        },
    )
    return out
