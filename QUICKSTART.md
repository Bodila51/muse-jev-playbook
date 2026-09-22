# Quickstart (5 minutes)

## Track A — Developer (any agent runtime)

You need a TypeSafe API key ([docs.typesafe.ai](https://docs.typesafe.ai)).

```bash
git clone https://github.com/Bodila51/muse-jev-playbook.git
cd muse-jev-playbook
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp config.example.yaml config.yaml
export TYPESAFE_API_KEY=...   # secret manager preferred; never commit the key
```

Run the offline-safe dry run (no Jev calls — kill switch path):

```bash
# edit config.yaml: enabled: false
.venv/bin/python scripts/dry_run.py
```

Then enable and run one live decision:

```bash
.venv/bin/python -m src.cli '{"goal":"summarize today's AI agent news","kind":"research"}'
```

Copy `skill/jev-usage-router.SKILL.md`-style policy into your agent: see
[skill/jev-decision-layer.SKILL.md](skill/jev-decision-layer.SKILL.md) for the
exact workflow and the action table. Start with `mode: shadow` in
`config.yaml`; move to `mode: active` after reviewing `logs/runs.jsonl`.

## Track B — Agent (Muse/Hatch)

Nothing to install. The `custom.typesafe-ai` credential is already connected;
the agent calls Jev through its own tooling and never sees the raw key.

1. Read [skill/jev-decision-layer.SKILL.md](skill/jev-decision-layer.SKILL.md).
2. Before expensive work (browser, deep research, retries, subagents), build the
   compact state from the skill and ask Jev.
3. Apply [docs/policy.md](docs/policy.md): act on confidence ≥ 0.80, surface
   0.50–0.79, escalate below 0.50.
4. Log each decision (goal, action, confidence, outcome) for calibration —
   see [docs/measurement.md](docs/measurement.md).
5. Keep the kill switch: if the user writes `bypass jev` / `no jev`, skip Jev
   entirely and work normally.

## Verify it works

- Track A: `scripts/dry_run.py` prints five decisions and writes
  `logs/runs.jsonl`. With `enabled: false` it must print `proceed_full` with
  `jev_used: false` for every case and make zero network calls.
- Track B: ask the agent a trivial question ("what is 2+2?") and a research
  question; the first should resolve to `chat_only`, the second to
  `research_capped` or `proceed_full`, each with a logged confidence.

If anything fails, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
