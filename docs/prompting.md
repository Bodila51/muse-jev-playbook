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
