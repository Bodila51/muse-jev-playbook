#!/usr/bin/env python3
"""Offline policy test: exercise decide_action with stubbed Jev outputs (no network).

Run: .venv/bin/python scripts/test_policy.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.router import decide_action, normalize_state  # noqa: E402


def stub(intent="research", conf=0.9, reuse=0.1, sub=0.1, stop=0.1, score=1.0,
         probs=None):
    return SimpleNamespace(
        choices={"intent": SimpleNamespace(choice=intent, confidence=conf,
                                           probabilities=probs or {intent: conf})},
        nouls={
            "reuse_cache": SimpleNamespace(noul=reuse),
            "needs_subagent": SimpleNamespace(noul=sub),
            "stop_retry": SimpleNamespace(noul=stop),
        },
        scores={"complexity": SimpleNamespace(score=score)},
    )


CFG = {"thresholds": {"min_choice_confidence": 0.55, "reuse_min": 0.65,
                      "subagent_min": 0.75, "stop_retry_min": 0.55},
       "limits": {"max_browser_sources": 5, "max_retries_same_error": 1}}

CASES = [
    # (state, stub kwargs, expected action)
    ({"goal": "2+2?", "kind": "chat"},
     {"intent": "chat", "conf": 0.95}, "chat_only"),
    ({"goal": "check order status", "kind": "lookup"},
     {"intent": "lookup", "conf": 0.9}, "run_deterministic"),
    ({"goal": "news brief", "kind": "research", "cached_artifact": True,
      "cached_note": "fresh"}, {"reuse": 0.9}, "reuse_cache"),
    ({"goal": "retry scrape", "kind": "browser", "prior_error": "timeout",
      "same_error_count": 2}, {"stop": 0.8}, "stop_retry"),
    ({"goal": "send email now", "kind": "account"},
     {"intent": "account", "conf": 0.99}, "ask_human"),
    ({"goal": "deep market research", "kind": "research"},
     {"intent": "research", "conf": 0.9}, "research_capped"),
    ({"goal": "big parallel investigation", "kind": "research"},
     {"intent": "research", "conf": 0.9, "sub": 0.85}, "allow_subagent"),
    ({"goal": "vague thing", "kind": "research"},
     {"intent": "research", "conf": 0.4}, "research_capped"),  # low conf still caps
    ({"goal": "bypass jev please", "kind": "research"},
     {"intent": "research", "conf": 0.9}, "research_capped"),  # bypass handled in route_task, not here
]


def main() -> int:
    failed = 0
    for i, (state, kw, expected) in enumerate(CASES, 1):
        action, reason, _ = decide_action(normalize_state(state), stub(**kw), CFG)
        ok = action == expected
        failed += not ok
        print(f"{'ok ' if ok else 'FAIL'} case {i}: got {action}, want {expected} ({reason})")
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
