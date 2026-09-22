# Troubleshooting

## Auth errors (Track A)

**`TYPESAFE_API_KEY is missing`** — the key must be in the process environment. `export TYPESAFE_API_KEY=...` before running, or use your secret manager. The code never reads key files; that's intentional.

**401 / 403 from api.typesafe.ai** — this is a question about the *request* before it's a question about the key:
1. Verify the request actually carried the credential (bearer header) via your client/SDK.
2. Check the key value for truncation or pasted whitespace.
3. Check the account's access/entitlements.
Only after an attached-credential request is still rejected should you rotate/replace the key.

**Track B (Muse/Hatch): never do any of the above.** The `custom.typesafe-ai` credential is managed by the connector. If a call fails with 401/403, check the request first; only then re-run the connector's access flow. Never ask the user to paste a key in chat.

## Model choice

- `jev-latest` — default, current stable.
- `jev-preview` — upcoming behavior; good for testing new question packs in shadow before they go active.
- Pin the model per question pack in `config.yaml` once validated; don't float production gates on `latest` without re-validating.

## Low confidence everywhere

- Shorten the state (goal + facts + constraints; see [docs/prompting.md](docs/prompting.md)).
- Split compound `noul` questions; sharpen `choice` criteria definitions.
- Check language: English states are the most accurate. If the task is non-English, test confidence on your own data first.
- Some tasks are genuinely ambiguous — that's what the 0.50–0.79 band is for. Don't force high confidence; surface instead.

## Timeouts / slowness

Jev calls are typically ~1s. On timeout: fall back to the normal agent path, log `jev_used: false`, and keep going. If timeouts persist, check network egress and the SDK version (`pip install -U typesafe-sdk`).

## Kill switch not working

Checklist: `config.yaml` has `enabled: false` (Track A reads `config.yaml`, falling back to `config.example.yaml` — make sure you're editing the right file); the bypass markers are `bypass jev` and `no jev` matched case-insensitively against goal/raw/message/notes. Track B: the skill checks the markers before building the state.

## Unexpected actions in active mode

The router maps Jev outputs through thresholds in `config.yaml` (`thresholds`, `limits`). If `reuse_cache` fires too eagerly, raise `reuse_min`; if the agent spawns subagents too often, raise `subagent_min`. Every change should be validated against the decision log first ([docs/measurement.md](docs/measurement.md)).

## Jev disagrees with the agent repeatedly

Log the overrides (see `agent_did` vs `action` in the log schema). If the agent is right >50% of overrides, the question pack is miscalibrated for your workload — rewrite the questions, don't just lower thresholds.
