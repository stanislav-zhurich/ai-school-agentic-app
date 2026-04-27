# Groundedness Rubric (1–3)

Used as a secondary, qualitative metric for a representative subset of eval rows.

## Scale

| Score | Criteria |
|-------|----------|
| **3 — Grounded** | The answer directly cites specific facts returned by a tool (e.g., exact temperature, a named news headline, a publication date). No factual hallucination detected. |
| **2 — Partially grounded** | The answer references the tool domain correctly but omits key specifics, or paraphrases loosely without citation. Minor hallucination risk. |
| **1 — Not grounded** | The answer ignores tool results, answers from memory/training data, or adds significant unsupported claims. |

## Instructions for manual/LLM-as-judge scoring

1. Show the evaluator: (a) the original question, (b) the raw tool output from the trace, (c) the agent's final answer.
2. Ask: "Does the answer cite facts consistent with the tool output above?"
3. Assign 1, 2, or 3 per the scale. When in doubt, prefer the lower score.
4. Record the score in the `rubric_score` field of the results JSON.

## Subset recommendation

Score all rows where `expected_domain` is `"weather"` or `"both"` — these tend to have the most verifiable numeric facts (temperature, precipitation, wind speed).
