# Prompting: writing states and questions that get high-confidence answers

Jev's accuracy is dominated by input quality. These rules come from production use; each has a failure mode attached.

## State rules

1. **One line for the goal.** `"Find the cheapest City A → City B round trip in April 2027"` beats a paragraph. If you can't state the goal in one line, the agent doesn't understand the task yet — fix that first.
2. **English is the most accurate.** Other languages work, but verify confidence on your own data before trusting high-stakes calls.
3. **Facts, not prose.** `kind_hint`, booleans (`has_cached_artifact`), counts (`same_error_count`, `sources_found`), short notes. Leave out backstory.
4. **Redact before judging.** Strip API keys, tokens, emails, and private user content from the state. Jev needs the *shape* of the task, not its payload.
5. **Include the decision-relevant context only.** For a retry gate: the last error and how many times it repeated. For a cache gate: what the artifact covers and how fresh it is. Nothing else.

## Question rules

1. **One proposition per `noul`.** "Should we stop retrying the same approach?" — good. "Should we stop and notify the user?" — bad; split into two questions.
2. **Criteria are definitions, not labels.** In `choice`, each option's description is what Jev actually classifies against. `"lookup": "Known file/API/status check; mostly deterministic"` beats `"lookup": "a lookup"`.
3. **4–8 sharp options beat 20 fuzzy ones.** If two criteria overlap, merge them; overlap bleeds probability mass and tanks confidence.
4. **Ordered `score` scales need real order.** `["trivial", "normal", "heavy"]` works because the levels are monotonic. Don't use score for unordered categories — that's what choice is for.
5. **Ask about the decision, not the world.** "Should this research be capped at 5 sources?" (actionable) beats "Is this research complex?" (vague). Jev is a decision layer; phrase questions as the decision you're about to make.
6. **Parallel questions, one call.** Intent classification + retry gate + effort score ride the same state in one call. Don't serialize what can be parallel — it's slower and no more accurate.

## Common mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Expecting prose | Trying to read an explanation out of Jev | Jev returns typed values; the agent writes the explanation |
| Secrets in state | Keys/tokens in logs | Redact first; log decisions, not payloads |
| Compound noul | Confidence stuck ~0.5 | Split into single propositions |
| Overlapping criteria | Probability split across two near-identical options | Merge or sharpen definitions |
| 200-word state | Low confidence, slow calls | Compress to goal + facts + constraints |
| Asking Jev to do the work | "Research X and tell me" as a question | Jev judges; the agent works |

## Measured: an explicit rubric in the question changed the result

The heuristics above are design guidance. One of them — that Jev's accuracy is
dominated by input quality — has now been partly tested on a bounded canary,
with a large enough effect to be worth acting on.

**Setup.** Twelve synthetic cases over a two-boolean state
(`operator_approval`, `reversible`), scored against a pre-registered
deterministic oracle. Cases, states, expected labels, scoring rule, and a
7/12 "constant answerer" floor were held identical between runs. The **only**
variable was the question's `instructions` text. Model `jev-1.13-20260917`
(provider `TypeSafe`, `POST /api/alpha/decisions`); 12 calls per arm.

| question phrasing | agreement |
|---|---|
| Terse — *"How ambiguous is this bounded state?"* | **5/12** (below the 7/12 floor) |
| Rubric-complete — *"Count the restrictive keys… 0 → none; 1 → weak; 2 → strong."* | **12/12** |

Under the terse prompt, `route_choice` returned the **same answer for all four
cases** — indistinguishable from an answerer that never varies. Under the
rubric it alternated correctly.

**What was actually varied.** Only the `instructions` wording of the
*ambiguity* question above. The template's own `complexity` question was **not**
tested; it is cited here only as an example of the same terse style, which the
canary suggests is the risk, not as a measured failure.

**What this does not show.** n=12, one endpoint, one model, one run, a
synthetic two-boolean state. The rubric was hand-written, so this measures
whether Jev can *apply* a stated rule, not whether it exercises good judgment.
A ceiling effect is likely: 12/12 on two booleans may be the maximum obtainable
score and tells you nothing about headroom. The registered interpretation for
the 12/12 arm is `rubric_following_works_not_judgment`.

**The practical rule.** If a question needs a definition to be answerable, put
the definition in the question. Do not rely on Jev inferring what you meant.

The `complexity` question in the template below is deliberately terse
(`"How much agent effort is justified?"`). It was not measured, but it is the
same style that scored 5/12 above, so it carries the same risk. If you keep it,
give it a rubric — name what makes something `trivial` versus `heavy`:

```json
"complexity": {
  "type": "score",
  "instructions": "Score the effort this work needs. Use trivial if it is a single known lookup or edit; normal if it needs a handful of steps across known tools; heavy if it needs multi-step planning, several tools, or new research. Answer with the matching label.",
  "criteria": ["trivial", "normal", "heavy"]
}
```

Note this is still a `score` over an ordered scale, per rule 4 above — the
change is that the boundaries are now stated rather than assumed.

**Reproducing this.** The measurement is a two-arm prompt A/B: hold your state,
expected labels, and scoring fixed, and change only the `instructions` text.
The guard that makes it trustworthy is pinning a digest of the instruction
string per question type, so you cannot accidentally tune the prompt to the
cases and call it a result. Score against a constant-answerer floor rather than
against zero — on a small skewed corpus those differ a lot.

Full receipts, the pre-registration, and the tamper tests for the run above
are held outside this repository (private workspace) because they record
provider responses. Ask if you want them; the headline is reproducible from
this recipe.

## A template worth copying

```json
{
  "state": {
    "goal": "<one line>",
    "kind_hint": "chat|lookup|research|browser|coding|write|account",
    "has_cached_artifact": false,
    "cached_note": "<scope + freshness, or empty>",
    "prior_error": "<last error, or empty>",
    "same_error_count": 0,
    "sources_found": 0,
    "constraints": "<hard limits, or empty>"
  },
  "questions": {
    "intent": {"type": "choice", "instructions": "What kind of work does this request mainly need?", "criteria": {"<opt>": "<sharp definition>"}},
    "reuse_cache": {"type": "noul", "instructions": "Is there a fresh enough cached result to reuse instead of new heavy work?"},
    "stop_retry": {"type": "noul", "instructions": "Given prior_error and same_error_count, should we STOP retrying the same approach?"},
    "complexity": {"type": "score", "instructions": "How much agent effort is justified?", "criteria": ["trivial", "normal", "heavy"]}
  }
}
```

See `recipes/` for six ready-made packs built on this template.
