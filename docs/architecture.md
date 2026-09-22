# Architecture: where the decision layer sits

The decision layer is **external and advisory** — it does not modify the agent's model, intercept tool calls, or run before the agent wakes. The agent must wake, build a state, and ask Jev. What makes it effective is *placement*: the call happens before the expensive fork in the road, not after.

```text
user request
    |
    v
agent wakes, loads the skill
    |
    +--> kill switch? (enabled: false, or "bypass jev" / "no jev") --yes--> normal path
    |
    v
is expensive work ahead? (browser / deep research / retry /
several skills / subagent / irreversible action)
    |                                   |
    no                                  yes
    |                                   v
    v                         build compact state {goal, kind,
proceed normally          cache hints, error history, constraints}
                                        |
                                        v
                              one Jev call: choice + score
                              + noul in parallel
                                        |
                                        v
                              policy on confidence:
                              >=0.80 act | 0.50-0.79 surface |
                              <0.50 escalate
                                        |
                                        v
                    +---------------------------------------+
                    | reuse_cache   use the fresh artifact   |
                    | stop_retry    explain, change approach |
                    | run_deterministic  bounded lookup     |
                    | chat_only     answer directly          |
                    | research_capped  at most N sources     |
                    | allow_subagent  spawn specialist       |
                    | ask_human     pause for approval       |
                    | proceed_full  normal work              |
                    +---------------------------------------+
                                        |
                                        v
                              log decision: goal, action,
                              confidence, outcome
```

## The feedback loop is the product

The router alone is a one-shot optimization. The durable value is the **decision log**: every call records what Jev recommended, at what confidence, and what actually happened. Review it weekly to:

- recalibrate thresholds (are 0.80+ actions actually succeeding?),
- sharpen question criteria (which questions come back low-confidence?),
- find new gates (where does the agent still burn effort without asking?).

See [measurement.md](measurement.md).

## What this architecture does not do

- **No pre-wake hook.** Nothing here reduces the cost of the agent waking up. The gate runs after wake, before expensive tools.
- **No enforcement.** In shadow mode the decision is advisory; in active mode it is honored only because the agent's skill says so. An agent that ignores the skill ignores the gate.
- **No safety bypass.** Irreversible actions keep their own confirmation path. Jev's `ask_human` is a second tripwire, not a replacement for it.
- **No credential flow.** Track A reads `TYPESAFE_API_KEY` from the environment only. Track B never touches a key at all.

## Failure behavior

If Jev is disabled, bypassed, slow, or errors: fall back to the normal agent path. Never invent a decision, never block the user on a classifier outage. Log the fallback like any other decision (`jev_used: false`) so outages are visible in review.
