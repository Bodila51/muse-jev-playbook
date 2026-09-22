# muse-jev-playbook

Use [TypeSafe AI's Jev](https://docs.typesafe.ai) as a cheap, fast decision layer inside an AI agent workflow — triage, classify, score, and gate work **before** expensive steps (browser, deep research, retries, subagents).

This is a practical, agent-oriented playbook: concepts, a confidence policy, copy-paste question recipes, a drop-in skill, and a real-world case study. It is adapted from [grok-bot-jev](https://github.com/Bodila51/grok-bot-jev) and generalized for any agent runtime (Muse/Hatch, custom harnesses, or plain scripts).

Jev does not generate text. It answers three typed question primitives in one parallel pass — `choice`, `score`, `noul` — each with probabilities and a confidence value (0–1) your code or agent can branch on. One Jev call costs a fraction of a cent and typically returns in about a second.

## Two ways to use this repo

**Track A — Developer (any runtime).** Install the TypeSafe SDK, set `TYPESAFE_API_KEY`, run the router in `src/` or the recipes in `recipes/`. See [QUICKSTART.md](QUICKSTART.md).

**Track B — Agent (Muse/Hatch).** The credential is already connected; the agent calls Jev through its tooling and follows [skill/jev-decision-layer.SKILL.md](skill/jev-decision-layer.SKILL.md). No key handling, ever.

Both tracks share the same concepts, policy, and recipes.

## What's inside

- `docs/concepts.md` — what Jev is: the three primitives, confidence, parallel questions
- `docs/architecture.md` — where the decision layer sits in an agent loop
- `docs/policy.md` — confidence thresholds: when to act, when to surface, when to escalate
- `docs/prompting.md` — how to write states and questions that get high-confidence answers
- `docs/measurement.md` — shadow → active rollout and how to measure the effect honestly
- `skill/jev-decision-layer.SKILL.md` — drop-in skill: when to call Jev and how to honor the result
- `recipes/` — six ready-made question packs: triage, rank options, act-or-wait, retry gate, research cap, approval gate
- `examples/flights-sep-2026.md` — real case: picking flight dates with Jev (with numbers)
- `examples/cli-usage.md` — calling Jev from the shell
- `examples/ab-template.json` — template for your own before/after measurements
- `TROUBLESHOOTING.md` — auth errors, model choice, low confidence, timeouts

## The core loop

```text
user request
    |
    v
agent wakes, checks kill switch ("bypass jev" / "no jev" / enabled: false)
    |
    v
build a compact state {goal, kind, cache hints, error history, constraints}
    |
    v
one Jev call: choice + score + noul questions in parallel
    |
    v
policy: act (>=0.80) | surface (0.50-0.79) | escalate (<0.50)
    |
    v
reuse_cache | stop_retry | run_deterministic | chat_only |
research_capped | allow_subagent | ask_human | proceed_full
    |
    v
log the decision (goal, action, confidence, outcome) for calibration
```

Start in **shadow mode** (log advice, act normally), review the log, then switch to **active mode** (honor the action). The kill switch always wins.

## A 30-second example

State: `{"goal": "Find the cheapest City A to City B round trip in April 2027", "kind": "research"}`

Questions (one call):
- `choice` "What kind of work does this need?" → `research` (confidence 0.93)
- `noul` "Should we cap this research at 5 sources instead of going deep?" → yes (0.88)
- `score` "How much effort is justified?" → `Heavy` (0.71)

Policy: confidence ≥ 0.80 → act. Result: `research_capped` at 5 sources. The agent skips the exhaustive scan and still answers the question.

## Honest limits

- Jev is one more network call; it can be wrong, unavailable, or slower than the work it would skip. Keep the kill switch and a safe fallback (normal path).
- Shadow mode enforces nothing; active mode only works if the agent honors the action.
- Jev never sends, publishes, pays, deletes, or changes permissions. Those stay behind human confirmation no matter what Jev says.
- The A/B numbers in `examples/` are from one local run — a method template, not a benchmark or a savings guarantee.

## Links

- [TypeSafe documentation](https://docs.typesafe.ai)
- [grok-bot-jev](https://github.com/Bodila51/grok-bot-jev) — the original Grok Bot reference this playbook generalizes

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

MIT. See [LICENSE](LICENSE).
