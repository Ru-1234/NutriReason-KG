# Manual review of the 10-CQ evaluation (answers in `results/eval_raw.json`)

Same model (`openai/gpt-oss-120b`, Groq), temperature 0, for A (LLM only) and B (LLM + KG). "Correct" = automatic checker in `run_eval.py` against sets computed with independent SPARQL; "unsupported claim" = a specific claim in the answer that the graph contradicts or does not contain (judged by hand).

| CQ | A correct | B correct | Unsupported claims in A | Unsupported claims in B |
|---|---|---|---|---|
| CQ1 | No | Yes | Pad Thai, pesto, baklava ... not in the KG; misses Kheer/Rabri/Rasmalai | 1: "Peanut Butter" listed as a dish (it is a food node; the answer said "dishes") |
| CQ2 | No | Yes | Generic categories only, no KG foods | 0 |
| CQ4 | No | Yes | "Big 8" groups (eggs, shellfish...) not the KG ranking | 0 |
| CQ5 | No | Yes | "condiments & sauces ~6000 mg" (not a KG group; wrong value) | 0 |
| CQ8 | No | Yes | adds egg and soy allergy, soy lecithin (not in the dish record); misses Type 2 diabetes <- Sugar | 0 |
| CQ9 | No | Yes | none strictly false: approximate 0.5 g / 620 mg, correct pass/fail, but not the exact values asked | 0 |
| CQ11 | No | Yes | "Big 8" list (eggs, peanuts, fish) vs KG: Dairy 137, Sugar 62, Wheat 59 | 0 |
| CQ12 | No | Yes | Pesto, Pad Thai, mole... (not in KG) | 0 |
| CQ13 | No | Yes | per-serving figures (cured ham 2,200 mg...) not KG values; unit mismatch | 0 |
| CQ14 | No | Yes | cites AHA / DASH; the KG rule's source is WHO | 0 |

Totals: correct A = 0/10, B = 10/10. Answers with unsupported claims: A = 9/10, B = 1/10. Evidence available: A = 0/10, B = 10/10 (every B answer cites fact ids [F..]).

## Caveats (be honest in the viva)
- The 10 questions were also used to debug the retriever (e.g. entity-linking tie-breaks, routing of "above the limit" questions), so B = 10/10 is a **development-set** score. `unseen_check.py` runs 8 other questions (results in `results/unseen_questions.md`); two of them exposed retriever gaps (low-sugar rule missing from the context; allergens without a linked condition, e.g. gluten) that were then fixed.
- A is judged against the KG's own data. For several questions (CQ4, CQ5, CQ11, CQ13) the LLM's general-knowledge answer is *plausible in the real world* but is a different question from "what does this graph say"; that is exactly the gap the project targets.
- The correctness checkers are keyword/set based (e.g. CQ4 requires "dairy" and "181"); they can pass an answer that mixes in a wrong item (the one case found is the CQ1 "Peanut Butter" mislabel in B).
- Retrieval lists are capped (12-15 rows): for long lists B gives a correct partial answer and says so.
- "Safe" = absence of an unsafeFor fact (open world); some foods have no allergen data.
