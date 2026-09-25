# Troubleshooting

## Auth errors (Track A)

Load `TYPESAFE_API_KEY` into the child-process environment only through a secret manager or another protected local injection mechanism. The code intentionally reads process environment variables, not key files. Never put the value in a project file, command argument, shell history, log, or chat.

**401 / 403 from the selected API** — this is a question about the *request* before it's a question about the key:
1. Verify via your client/SDK that the request used the selected credential path, without displaying or inspecting the value.
2. Use a non-disclosing presence/status check from the secret manager or client to detect injection or configuration issues; never print, paste, or otherwise expose the value.
3. Check the account's access/entitlements.
Only after an attached-credential request is still rejected should you rotate/replace the key.

**Track B:** do not assume a connector exists or is authenticated. Use only a connector already attached and verified by the host; if unavailable, keep the route disabled. Never ask the user to paste a key in chat.

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

On timeout or provider failure: fall back to the normal agent path, record `jev_used: false` with bounded metadata, and keep going. Do not claim Jev decided. If timeouts persist, check network egress and the pinned SDK version rather than upgrading it during a live investigation.

## Kill switch not working

Checklist: `config.yaml` has `enabled: false`; the loader never falls back to `config.example.yaml`, and that example is disabled too. The bypass markers are `bypass jev` and `no jev` matched case-insensitively against goal/raw/user_message/message/notes. Track B: the skill checks the markers before building the state.

## Unexpected actions in active mode

The router maps Jev outputs through thresholds in `config.yaml` (`thresholds`, `limits`). If `reuse_cache` fires too eagerly, raise `reuse_min`; if the agent spawns subagents too often, raise `subagent_min`. Every change should be validated against the decision log first ([docs/measurement.md](docs/measurement.md)).

## Jev disagrees with the agent repeatedly

Record overrides in a separate experiment note (for example, `agent_did` versus
`action`); the project JSONL audit intentionally stores only bounded route
metadata. If the agent is right >50% of overrides, the question pack is
miscalibrated for your workload — rewrite the questions, don't just lower
thresholds.
