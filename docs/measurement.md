# Measurement: shadow → active rollout done honestly

The point of measuring is calibration, not marketing. A decision log tells you which questions earn enforcement and which need rewriting.

## The rollout ladder

1. **Shadow (1–2 weeks).** Jev returns recommendations; the agent acts on normal judgment. Log everything: state summary, questions, answers, confidence, what the agent actually did, and the outcome.
2. **Review.** For each question pack, bucket decisions by confidence band (≥0.80 / 0.50–0.79 / <0.50) and check: were high-confidence recommendations right? How often did the agent override medium ones, and who was right?
3. **Active, per pack.** Promote a question pack to enforcement only when its high-confidence band is right ≥ 9 times out of 10 on your log. Keep the rest in shadow.
4. **Recalibrate quarterly.** Tasks drift; re-run step 2. Demote packs that decay.

## What to log (JSONL, one line per decision)

```json
{"ts": "2026-09-22T10:15:00Z", "goal": "Find cheapest CityA-CityB April 2027 RT",
 "questions": ["intent", "reuse_cache", "research_cap"],
 "action": "research_capped", "confidence": 0.88, "mode": "shadow",
 "agent_did": "capped at 5 sources", "outcome": "ok",
 "jev_used": true, "ms": 900}
```

Never log secrets, raw user content, or credentials — log the decision, not the payload. See `examples/ab-template.json` for a starter schema and aggregation sketch.

## What counts as evidence (and what doesn't)

**Counts:**
- Paired before/after on the same tasks: tool calls avoided, retries stopped, sources fetched, wall time, Jev cost.
- Override analysis: when the agent ignored a medium-confidence recommendation, who was right?
- Confidence calibration: do 0.80+ decisions succeed ~95%+ of the time?

**Doesn't count:**
- Weekly usage meters that include unrelated chat overhead (noisy proxy).
- Reused-cache wins presented as cold-start wins (say which it was).
- Timing comparisons where one arm was capped by design (report the cap, don't imply disappearance).
- Any single local run presented as a benchmark or a savings guarantee.

## A minimal honest report

For each experiment, publish: the task list, both arms' raw counts, Jev cost, the exact caps applied, and a caveats section. `examples/flights-sep-2026.md` follows this format. If exact token/dollar figures for the main model aren't available, say so explicitly instead of substituting a proxy meter.

## Kill criteria

Demote or rewrite a question pack if: high-confidence accuracy < 90% over 30+ decisions, chronic 0.50–0.65 confidence (the question is malformed — see [prompting.md](prompting.md)), or Jev latency/cost exceeds the work it gates. A gate that doesn't pay for itself is overhead, not optimization.
