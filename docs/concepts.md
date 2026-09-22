# Concepts: what Jev is

Jev is TypeSafe AI's "System One" model: fast, typed judgments instead of generated text. Think of it as the reflex layer of an agent — the part that decides *what kind of work this is* and *how much effort it deserves* before the slow, expensive reasoning starts.

## The three primitives

Every Jev call takes a **state** (what the situation is) and a set of **questions** (what you want judged). All questions are evaluated in one parallel pass against the same state.

**choice** — pick one of N named options.
```json
{"type": "choice",
 "instructions": "What kind of work does this request mainly need?",
 "criteria": {
   "chat": "Short answer or conversation; no tools needed",
   "lookup": "Known file/API/status check; mostly deterministic",
   "research": "Needs web/search and synthesis",
   "browser": "Needs interactive browser clicks",
   "coding": "Edit code, tests, repo work",
   "account": "Send, publish, pay, delete, change permissions"
 }}
```
Returns `choice`, per-option `probabilities`, and `confidence` (0–1). Up to 255 criteria allowed, but 4–8 sharp ones beat 20 fuzzy ones.

**score** — place the state on an ordered scale.
```json
{"type": "score",
 "instructions": "How much agent effort is justified?",
 "criteria": ["trivial", "normal", "heavy"]}
```
Returns `score` (mean), per-level probabilities, a `legend` mapping index → label, and `confidence`. Use it for effort, urgency, risk, or quality judgments.

**noul** — a yes/no proposition ("noul" = yes/no).
```json
{"type": "noul",
 "instructions": "Given the prior error and retry count, should we STOP retrying the same approach?"}
```
Returns P(yes) from 0 to 1. One proposition per question — compound questions ("should we stop and notify?") split into two.

## Confidence is the whole game

Every answer carries `confidence` 0–1. The playbook's policy ([policy.md](policy.md)) branches on it:

- **≥ 0.80** — act on the answer autonomously
- **0.50–0.79** — treat as a recommendation; proceed carefully or surface it
- **< 0.50** — escalate to the human

Thresholds scale with the cost of being wrong: irreversible actions need human confirmation regardless of confidence.

## What Jev is not

- **Not a text generator.** It returns typed values, not prose. If you need an explanation, your agent writes it from the typed result.
- **Not a worker.** It doesn't browse, research, code, send, or pay. It only judges.
- **Not a permission.** A high-confidence Jev answer never authorizes revealing secrets, bypassing safety rules, or skipping confirmations.
- **Not infallible.** It can misclassify, especially on vague states or out-of-distribution tasks. That's why shadow mode, logging, and the kill switch exist.

## Cost and latency shape

A Jev call is typically ~1 second and a fraction of a cent — orders of magnitude cheaper than a browser session, a deep research pass, or a wasted subagent. The entire economic argument of this playbook: spend a tiny, bounded classification call to avoid unbounded expensive work.

## State design (the 80/20)

Keep the state compact and factual: the goal in one line, a kind hint, cache freshness, error history, hard constraints. English states are the most accurate; other languages work but verify confidence on your own data. Never put secrets, credentials, or private user content in the state — redact first, then judge.

See [prompting.md](prompting.md) for the full guide.
