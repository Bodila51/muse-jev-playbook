# CLI usage examples

## Track A — Developer track (`typesafe-sdk`)

One-off decision from a JSON state:

```bash
# Inject TYPESAFE_API_KEY into the process environment through a secret manager.
# Do not put the value in a file or command argument.
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

The agent may use a credential connector only when the host has already attached and verified it. This repository makes no connector-availability claim and the agent never receives a raw key. The equivalent of the triage call above is: build the state
from `skill/jev-decision-layer.SKILL.md`, ask the recipe's questions in one
parallel call, apply `docs/policy.md` thresholds, log the decision.

Example decision log line (JSONL, with task text omitted):

```json
{"ts":"2026-09-22T10:15:00Z","goal_sha256":"<sha256>",
 "provider":"experientiallabs_native","model":"jev-latest",
 "action":"research_capped","mode":"shadow",
 "primitive_counts":{"choice_count":1,"noul_count":3,"score_count":1},
 "jev_used":true}
```

## Reading the output

`action` is the verb, `reason` is the one-line why, and CLI `details` carries the typed Jev values returned to the caller (intent + confidence + probabilities, noul P(yes) values, complexity). Those values are not written to the JSONL audit. In shadow mode the agent logs bounded metadata and uses normal judgment; in active mode it honors `action`. See `docs/policy.md` for the threshold table.
