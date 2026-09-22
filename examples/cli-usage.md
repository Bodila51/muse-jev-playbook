# CLI usage examples

## Track A — Developer track (`typesafe-sdk`)

One-off decision from a JSON state:

```bash
export TYPESAFE_API_KEY=...
.venv/bin/python -m src.cli '{"goal":"summarize today AI agent news","kind":"research"}'
```

With a recipe file (fill `_state_template` first):

```bash
# recipes/triage.json -> copy _state_template, set your goal, save as /tmp/state.json
.venv/bin/python -m src.cli "$(cat /tmp/state.json)"
```

Retry gate after two identical failures:

```bash
.venv/bin/python -m src.cli '{
  "goal": "Scrape product prices from example.com",
  "kind": "browser",
  "prior_error": "timeout on selector .price",
  "same_error_count": 2
}'
# -> action: stop_retry (noul ~0.8), reason explains the stop
```

Approval gate before an irreversible action:

```bash
.venv/bin/python -m src.cli '{
  "goal": "Send refund email to customer ACME-042",
  "kind": "account"
}'
# -> action: ask_human (any confidence)
```

## Track B — Agent track (Muse/Hatch)

The agent calls Jev through its own tooling (credential `custom.typesafe-ai`,
never a raw key). The equivalent of the triage call above is: build the state
from `skill/jev-decision-layer.SKILL.md`, ask the recipe's questions in one
parallel call, apply `docs/policy.md` thresholds, log the decision.

Example decision log line (JSONL):

```json
{"ts":"2026-09-22T10:15:00Z","goal":"Summarize today's AI agent news",
 "questions":["intent","reuse_cache","research_cap"],"action":"research_capped",
 "confidence":0.88,"mode":"shadow","agent_did":"capped at 5 sources",
 "outcome":"ok","jev_used":true,"ms":900}
```

## Reading the output

`action` is the verb, `reason` is the one-line why, `details` carries the raw
Jev values (intent + confidence + probabilities, noul P(yes) values, complexity).
In shadow mode the agent logs the recommendation and uses normal judgment; in
active mode it honors `action`. See `docs/policy.md` for the threshold table.
