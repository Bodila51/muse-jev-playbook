# Contributing

Thanks for helping improve this playbook.

## Setup (Track A)

```bash
python3 -m venv .venv
# requirements.txt declares the direct dependencies; install the reproducible,
# hash-checked lockfile.
.venv/bin/pip install --require-hashes -r requirements.lock
cp config.example.yaml config.yaml
```

Set `TYPESAFE_API_KEY` in your environment for live Jev calls. For offline checks, set `enabled: false` in `config.yaml`.

## Checks before a PR

```bash
.venv/bin/python -m compileall src scripts
.venv/bin/python scripts/test_policy.py   # offline policy test, no network
# offline dry-run (kill-switch path):
.venv/bin/python - <<'EOF'
import yaml
from pathlib import Path
p = Path('config.yaml')
d = yaml.safe_load(p.read_text())
d['enabled'] = False
p.write_text(yaml.safe_dump(d))
EOF
.venv/bin/python scripts/dry_run.py
```

Live dry-runs against TypeSafe are optional and use your own key. Do not commit keys, `.env`, `config.yaml`, or logs.

Also validate the JSON recipes and examples:

```bash
.venv/bin/python - <<'EOF'
import json, glob
for f in glob.glob('recipes/*.json') + glob.glob('examples/*.json'):
    json.load(open(f))
    print('ok', f)
EOF
```

## Pull requests

- Keep changes focused; prefer small diffs with a clear why.
- Update README or docs when behavior changes.
- New recipes go in `recipes/` with `_description`, `_policy`, `_questions`, `_state_template`.
- Do not claim universal token savings; keep A/B notes as local proxy measurements with caveats (see `docs/measurement.md`).

## Scope

This project is a decision layer: skill + scripts + recipes + docs. It is not an agent middleware or pre-wake interceptor — please keep PRs aligned with that boundary.
