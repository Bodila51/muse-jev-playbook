# Quickstart (5 minutes)

## Track A — Developer (any agent runtime)

You need a TypeSafe API key ([docs.typesafe.ai](https://docs.typesafe.ai)).

```bash
git clone https://github.com/Bodila51/muse-jev-playbook.git
cd muse-jev-playbook
python3 -m venv .venv
# requirements.txt declares the direct dependencies; use the hash-locked file
# for the reproducible install.
.venv/bin/pip install --require-hashes -r requirements.lock
cp config.example.yaml config.yaml
# Inject TYPESAFE_API_KEY only into the child-process environment through your
# secret manager. Never place its value in files or command arguments.
```

Run the offline-safe dry run (no Jev calls — kill-switch path):

```bash
# config.example.yaml is disabled by default
cp config.example.yaml config.yaml
# edit config.yaml: enabled: false
.venv/bin/python scripts/dry_run.py
```

To use the separately labeled native route, set `provider: experientiallabs_native`, the explicit native base URL, and `credential_env: HERMES_CUSTOM_API_EXPERIENTIALLABS_AI_API_KEY` in the ignored local config. Do not rename that value to `TYPESAFE_API_KEY`. The official route remains separately selectable with `typesafe_official`.

Live calls are not enabled by copying the example or by running the dry run. After explicit credential setup and review, enable a live decision only in the ignored local config:

```bash
# After separate authorization and review, set enabled: true in config.yaml
.venv/bin/python -m src.cli '{"goal":"summarize today AI agent news","kind":"research"}'
```

Use the repository's [skill/jev-decision-layer.SKILL.md](skill/jev-decision-layer.SKILL.md)
as the policy/workflow reference for your agent. Start with `mode: shadow` in
`config.yaml`; move to `mode: active` only after reviewing `logs/runs.jsonl`.

## Track B — Agent (Muse/Hatch)

Nothing to install in this repository. Track B may use a credential connector only when the host has already attached and verified it; this project makes no connector-availability claim. The agent calls Jev through that host tooling and never sees a raw key.

1. Read [skill/jev-decision-layer.SKILL.md](skill/jev-decision-layer.SKILL.md).
2. Before expensive work (browser, deep research, retries, subagents), build the
   compact state from the skill and ask Jev.
3. Apply [docs/policy.md](docs/policy.md): act on confidence ≥ 0.80, surface
   0.50–0.79, escalate below 0.50.
4. Log each decision using bounded route metadata (goal SHA-256, action, mode, provider/model, primitive counts, and `jev_used`) for calibration — see [docs/measurement.md](docs/measurement.md). Do not retain the raw goal or answer payload in the project log.
5. Keep the kill switch: if the user writes `bypass jev` / `no jev`, skip Jev
   entirely and work normally.

## Verify it works

- Track A: `scripts/dry_run.py` prints five decisions and writes
  `logs/runs.jsonl`. With `enabled: false` it must print `proceed_full` with
  `jev_used: false` for every case and make zero network calls. The example
  config is not an activation source.
- Track B: ask the agent a trivial question ("what is 2+2?") and a research
  question; the first should resolve to `chat_only`, the second to
  `research_capped` or `proceed_full`. Any confidence is a response detail,
  not a persisted project-log field.

If anything fails, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
