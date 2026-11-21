# Retrieval layer (Maham Anjum, 24i-0053)

> All numbers below come from tthe runs on 22 Nov (`evaluation/results/routes_before.txt`, `routes_after.txt`).

## 1. What the retriever does

`retrieval/retriever.py` turns a user question into a small set of graph facts that the LLM is allowed to use.
It follows the retrieve-then-generate idea of RAG (Lewis et al., 2020), but the retrieved context is a list of
graph triples instead of text chunks, as in graph-based RAG (Edge et al., 2024; Peng et al., 2024).

1. **Entity linking.** Health conditions are found with an alias table ("diabetic" → Type 2 diabetes).
   Foods, dishes, ingredients, allergens and food groups are found by matching question words against the
   `rdfs:label` of every node (token coverage), with a fuzzy fallback for typos.
2. **Routing.** Keywords and the kinds of linked entities choose one SPARQL template
   (dish profile, food profile, unsafe list for a condition, safe-for list, both conditions, top nutrient,
   above-limit list, rule/guideline, group averages, allergen frequency, ...).
3. **SPARQL.** The template runs over two rdflib graphs: explicit (T-Box + A-Box) and inferred-only
   (`inferred.ttl`). Each fact gets an id (F1, F2, ...) and a tag `explicit` or `inferred`.
4. **Sufficiency.** If nothing useful was found, the retriever returns `sufficient = False` with a reason,
   and the grounded prompt tells the LLM to answer "Insufficient evidence in the knowledge graph".

We chose SPARQL templates over embedding search because the questions need exact numbers, thresholds and
multi-hop paths, and every fact a template returns can be traced back to a triple (Hogan et al., 2021).

## 2. Failures found and fixed (Iteration 2)

I wrote `evaluation/check_routes.py`, which prints one line per question (route type, sufficient, number of facts,
an 8-character hash of all retrieved facts and paths, linked entities) without calling the LLM. It runs the 10
evaluation CQs (same wording as `run_eval.py`) and 12 extra questions (X1–X12: unknown dishes, the sugar-limit
question, a typo, an off-topic question). I ran it **before** changing the retriever and **after** both fixes.
The 10 CQ lines had to stay identical; only the extra questions were allowed to change.

**Making the check repeatable.** The first "after" run reported 6 changed CQ lines, although every CQ kept the
same route type and 9 of 10 kept the same number of facts. The cause was not the fixes: some templates take
example rows from SPARQL queries without `ORDER BY` (e.g. the first ingredient of a dish, or `LIMIT 5`), and
rdflib returns such rows in an order that depends on Python's string-hash seed, which is random for every new
process. Two runs of the same code could therefore send slightly different example facts to the LLM. The
extra questions X7 and X8, which the fixes do not touch, changed in the same way. `check_routes.py` now always
runs with `PYTHONHASHSEED=0`, and with a fixed seed the old and new retriever give identical CQ lines.

### Fix A — unknown dish or food

* **Problem.** "Can I eat dragon fruit curry if I have a nut allergy?" was marked `sufficient = True`. The word
  "fruit" linked the food group *Fruit*, the question fell through to the general nut-allergy route, and
  35 unrelated facts (9 nut-allergy dishes and the rule chain) were sent to the LLM. "Is dragon fruit curry safe
  for type 2 diabetes?" returned 44 facts (a general safe-for list) and "Is unicorn stew ok for hypertension?"
  returned 28 facts (the 12 saltiest foods). In all three cases the retriever said the evidence was sufficient.
* **Fix.** After linking, the retriever lists the content words that no linked entity explains and that are not
  request words (eat, safe, allergy, limit, ...). If such words remain and no dish, food, ingredient or allergen
  was linked, a yes/no question (or a question that only matched a food group) gets the new route `unknown_item`:
  no facts, `sufficient = False`, and a reason that names the unmatched words, e.g.
  *"The item named in the question is not in the knowledge graph (unmatched words: 'dragon', 'curry'). Only Fruit (FoodType) matched, which is not the item asked about."*
* **Limit.** If one word of an unknown dish is itself a food (e.g. "mango lassi" → *Mango*), the food profile is
  still returned and the LLM prompt must decline, as before.

### Fix B — "sugar above the diabetes limit"

* **Problem.** "Which foods have sugar above the diabetes limit?" linked the ingredient *Sugar* and returned the
  profile of sugar itself (10 facts, route `food_profile`) instead of a list of foods.
* **Fix.** When the only food linked is the nutrient word itself (Sugar / Salt) and the question asks for values
  above / over / exceeding a limit, the new route `above_limit` runs. It reads the threshold from the rule node
  (22.5 g sugar per 100 g for type 2 diabetes, 600 mg sodium for hypertension), counts all foods above it, and
  returns the 15 highest with exact values, their `unsafeFor` link and the rule → guideline (ADA) chain: 38 facts.
* **Result.** 669 foods have sugar above 22.5 g per 100 g. The highest are *Sugars, Granulated* (99.80 g),
  *Sugar, Turbinado* (99.19 g) and *Sugars, Powdered* (97.81 g). The second wording ("Which foods exceed the sugar
  limit for type 2 diabetes?") gives the same 38 facts.

### Regression check

| Run | CQ lines changed | Extra questions with sufficient = False |
|---|---|---|
| before fixes | — | X3, X12 |
| after Fix A + B (`PYTHONHASHSEED=0`) | 0 | X1, X2, X3, X4, X12 |

X5 and X6 moved from `food_profile` to `above_limit`; X3 was already insufficient (route `group_members`, no
facts) and now gets the clearer `unknown_item` reason. X9–X11 are unchanged.

## 3. GraphDB

The cleaned graph was loaded into GraphDB 11.5.1 (repository `nutrireason`): T-Box + A-Box = 42,424 explicit
triples. GraphDB does not run SWRL, so the rules R1–R5 are written as SPARQL INSERT in `Ontology/rules_graphdb.ru`;
running it adds 7,609 inferred triples (42,424 → 50,033). This matches the offline rdflib count, so the
Python retriever (which loads the same files with rdflib) and GraphDB see the same graph. Iteration 1 added 7,673;
the 64 fewer come from removing the non-allergen labels from D1. Before the rules run, the inference queries
return 0 rows; after it, they return rows.

Screenshots (new KG, Iteration 2 reload):
* `Results/00_import_count.png` — 42,424 explicit triples after import
* `Results/01_sanity_BEFORE_rules.png`, `Results/02_CQ1_BEFORE_rules.png` — 0 inferred rows before the rules
* `Results/03_rules_executed.png`, `Results/03_import_count_AFTER_rules_executed.png` — rules run, 50,033 total
* `Results/03_sanity_AFTER_rules.png`, `Results/CQ1.png` … `Results/CQ14.png` — query results after the rules
* `Results/inference1_allergen.png`, `inference2_sodium.png`, `inference3_lowsugar.png` — the three inference examples
* `Visualization/graphdb_visual_graph.png`, `Visualization/graphdb_visual_graph_overview.png` — visual graph

## References

* Lewis, P. et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. *NeurIPS 2020*.
* Edge, D. et al. (2024). From Local to Global: A Graph RAG Approach to Query-Focused Summarization. arXiv:2404.16130.
* Peng, B. et al. (2024). Graph Retrieval-Augmented Generation: A Survey. arXiv:2408.08921.
* Hogan, A. et al. (2021). Knowledge Graphs. *ACM Computing Surveys*, 54(4), 1–37.
* W3C (2013). SPARQL 1.1 Query Language. W3C Recommendation.
