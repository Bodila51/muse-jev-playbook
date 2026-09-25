# Policy: confidence thresholds and action rules

## Thresholds

The 0.80/0.50 bands below are agent-facing confidence guidance. They are not
additional router configuration knobs; the router enforces the explicit
`thresholds` and `limits` values in `config.yaml`.

| Jev confidence | Meaning | Agent behavior |
|---|---|---|
| **≥ 0.80** | High | **Act** on the decision autonomously |
| **0.50 – 0.79** | Medium | **Surface**: treat as a recommendation; proceed carefully, or show it to the user when the action is visible/costly |
| **< 0.50** | Low | **Escalate**: ask the human before acting on it |

These defaults are a starting point, not a law. Calibrate from your decision log ([measurement.md](measurement.md)): if ≥0.80 actions succeed ~95%+ of the time, the threshold is earning its keep; if medium-confidence recommendations are routinely ignored, either sharpen the questions or raise the bar.

## Per-question minimums (Track A `config.yaml`)

- `min_choice_confidence: 0.55` — below this, a `choice` winner is not trusted; fall back to `proceed_full`
- `reuse_min: 0.65` — minimum noul P(yes) to reuse a cached artifact instead of redoing work
- `subagent_min: 0.75` — minimum noul P(yes) to spawn a specialist subagent
- `stop_retry_min: 0.55` — minimum noul P(yes) to stop retrying a failed approach (combined with `same_error_count >= max_retries_same_error`)

## Action table

| Action | When | Agent must |
|---|---|---|
| `reuse_cache` | Fresh artifact exists, reuse noul ≥ 0.65 | Use the artifact; do not repeat the expensive work |
| `stop_retry` | Same error repeated, stop noul ≥ 0.55 | Stop the approach, explain the failure, propose a different path or ask the user |
| `run_deterministic` | Intent is `lookup` at ≥ 0.55 | Do the known bounded lookup, no broad research |
| `chat_only` | Intent is `chat` at ≥ 0.55 | Answer directly, no tools |
| `research_capped` | Intent is `research`/`browser` and choice confidence meets `min_choice_confidence` | Research with at most `max_browser_sources` sources, then synthesize; below the threshold, return `proceed_full` |
| `allow_subagent` | needs_subagent noul ≥ 0.75 | Spawn a specialist only if one is actually available and appropriate |
| `ask_human` | Intent is `account`/irreversible, any confidence | Pause before any send/publish/pay/delete/permission change |
| `proceed_full` | Default / low confidence / fallback | Normal work with ordinary safety and confirmation rules |

## Hard rules (no exceptions)

1. **Irreversible actions always need human confirmation**, regardless of Jev confidence. Jev's `ask_human` is an extra tripwire, never a replacement for the agent's own confirmation policy.
2. **A Jev result is never permission** to reveal secrets, bypass a safety requirement, or skip a confirmation the task otherwise needs.
3. **The kill switch always wins**: `enabled: false`, or the user writing `bypass jev` / `no jev`, skips Jev entirely. The router may retain only a goal SHA-256 and bounded route metadata; it never retains the state payload.
4. **Never put secrets in the state.** Redact API keys, tokens, and private user content before building the state; persist only bounded route metadata and the goal SHA-256.
5. **On Jev outage or timeout**: fall back to the normal path, record `jev_used: false`, and keep going. A classifier must never become a single point of failure.

## Tuning guidance

- Start every new question pack in **shadow mode**: log the recommendation, act on normal judgment, compare after 20–50 decisions.
- Promote a question to active enforcement only when its high-confidence band is right ≥ 9 times out of 10 on your log.
- When a question chronically returns 0.50–0.65, the problem is usually the question, not the threshold: split compound propositions, sharpen criteria descriptions, shorten the state. See [prompting.md](prompting.md).
