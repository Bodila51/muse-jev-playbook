---
name: "jev_decision_layer"
description: "Use TypeSafe AI's Jev as a cheap, fast decision layer before expensive agent work (browser, deep research, retries, subagents). Call when a task is about to fork into costly tool use, a cached result might exist, an approach already failed, or an irreversible action is ahead."
---

# Jev Decision Layer

Jev (TypeSafe AI's "System One" model) gives fast typed judgments — `choice`, `score`, `noul` — with confidence 0–1. Use it as a gate **before** expensive work, not after. Jev never generates text, never browses, never sends/pays/publishes/deletes. It only judges; you still do the work and keep all safety rules.

## When to call

Call Jev when ANY of these is true:
- about to open a live browser, do multi-source research, or run a long tool chain
- retrying an approach that already failed (same error 2+ times)
- a fresh cached artifact or earlier result might already answer this
- about to load several specialized skills or spawn a subagent
- the request smells like an irreversible action (send, publish, pay, delete, permission change)

Skip Jev (kill switch) when: config has `enabled: false`, or the user wrote `bypass jev` / `no jev`. Then work normally and log nothing about Jev.

## Workflow

1. **Kill switch first.** Check config / user message for bypass markers. If set, skip everything below.
2. **Build a compact state** (English, one line for the goal, facts only, redacted):
```json
{
  "goal": "what the user wants, one line",
  "kind_hint": "chat|lookup|research|browser|coding|write|account",
  "has_cached_artifact": false,
  "cached_note": "scope + freshness, or empty",
  "prior_error": "last error, or empty",
  "same_error_count": 0,
  "sources_found": 0,
  "constraints": "hard limits, or empty"
}
```
3. **Ask in one parallel call.** Start from `recipes/` or the template in `docs/prompting.md`: an `intent` choice, a `reuse_cache` noul, a `stop_retry` noul, a `complexity` score. Add recipe-specific questions as needed.
4. **Apply the policy** (`docs/policy.md`):
   - confidence ≥ 0.80 → **act** on the decision
   - 0.50–0.79 → **surface** as a recommendation; proceed carefully
   - < 0.50 → **escalate** to the user
5. **Honor the action** (active mode) / **log the advice** (shadow mode):

| Action | Meaning |
|---|---|
| `reuse_cache` | Use the fresh artifact; don't redo the work |
| `stop_retry` | Stop the failed approach; explain and propose another path |
| `run_deterministic` | Do the known bounded lookup, no broad research |
| `chat_only` | Answer directly, no tools |
| `research_capped` | Research with at most N sources, then synthesize |
| `allow_subagent` | Spawn a specialist only if actually available/appropriate |
| `ask_human` | Pause before any irreversible action |
| `proceed_full` | Normal work with ordinary safety rules |

6. **Log the decision** (JSONL, one line): timestamp, goal (≤300 chars), action, confidence, mode, what you actually did, outcome (`ok` / `overridden` / `wrong`), `jev_used`, latency. Never log secrets or raw user content.

## Hard rules

- Irreversible actions ALWAYS need human confirmation, regardless of Jev confidence.
- A Jev result is never permission to reveal secrets or bypass safety/confirmation rules.
- On Jev error/timeout: fall back to the normal path, log `jev_used: false`, keep going.
- Keep states short; split compound yes/no questions; sharpen choice criteria when confidence sags (see `docs/prompting.md`).
- Start new question packs in shadow mode; promote to active only after the log shows high-confidence accuracy ≥ 90%.

## Honest limits

This skill is a policy, not a hook: the agent must wake and call Jev; nothing here reduces wake-up cost. Shadow mode is advisory. Active mode works only insofar as the agent honors the action. Jev can misclassify — the log and the kill switch are the correction mechanisms.
