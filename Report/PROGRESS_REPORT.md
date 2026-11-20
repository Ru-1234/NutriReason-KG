# NutriReason - Progress Report (Iteration 1 + Iteration 2 status)

Team: krr-08-nutrireason | Course: AI-3001 Knowledge Representation & Reasoning | Instructor: Ms. Mehreen Javaid

## 0. Team

| Member | Roll no. | GitHub username |
|---|---|---|
| Muhammad Zamin | 24i-0002 | `zamin-muhammad` |
| Romaisa | 24i-0061 | `Ru-1234` |
| Maham Anjum | 24i-0053 | `mahamanjum99` |

---

# PART A - ITERATION 1 (Knowledge Graph Construction & Symbolic Reasoning)

## A1. Completed work
- **Competency questions:** 14 CQs and a CQ-to-KG mapping table. Coverage: 7 multi-hop, 9 inference, 7 aggregation/filtering and 5 LLM-difficult questions (most CQs belong to more than one category).
- **Ontology (T-Box):** 12 core classes (plus allergen and condition subclasses and 3 inferred classes), 11 object properties, 5 datatype properties and reasoning constructs RC1-RC6 (subclass hierarchy, hasValue restriction, transitive property, inverse properties, property chain, and rules R1-R5). File: `Ontology/nutrireason_tbox.ttl`, viewed in Protege.
- **RDF knowledge graph (A-Box):** built by `build_kg.py` from D1-D4 (see A3). File: `RDF_Knowledge_Graph/abox.ttl`. Total triples: 42,424 (T-Box + A-Box; `abox.ttl` alone: 42,027), checked offline with rdflib. Re-check the count after reloading GraphDB.
- **GraphDB:** graph loaded into the `nutrireason` repository; visual graph screenshot in `Visualization/`.
- **Rules:** `rules_graphdb.ru` (SPARQL equivalents of R1-R5) run in GraphDB: +7,609 inferred triples (offline check, 50,033 total; Iteration 1 was +7,673 before the allergen clean-up, see B2).
- **SPARQL:** 14 queries (CQ1-CQ14), 3 inference demos (INF1-INF3) and a sanity query; outputs in `Results/`.

## A2. SPARQL feature coverage
| Required feature | Where |
|---|---|
| Basic graph patterns | CQ4, CQ5, CQ9 |
| FILTER | CQ2, CQ6, CQ9, CQ12, CQ13 |
| OPTIONAL | CQ9, CQ13 |
| UNION | CQ1, CQ2 (via binds), CQ8, 00_sanity_check |
| Aggregation (COUNT/AVG/GROUP BY) | CQ4, CQ5, CQ11, CQ6 (MAX, GROUP_CONCAT) |
| Multi-hop traversal | CQ1, CQ6, CQ8, CQ12, CQ14 |
| Property paths | CQ7 (`partOfCategory+`), CQ1 (`rdfs:subClassOf*`), CQ8 (`hasIngredient/containsAllergen`) |
| Inference-dependent | CQ1, CQ3, CQ8, CQ10, CQ12, CQ14, INF1-3 (0 rows before the rules run) |

## A3. Data cleaning / transformation (`build_kg.py`)
Full description: `Report/DATA_PIPELINE.md`.
- All CSVs read as text; headers and cells trimmed, whitespace collapsed, exact duplicate rows dropped.
- **D3 (USDA):** rows with missing or negative Calories/Sodium/Sugar removed; duplicate IDs and duplicate names removed; decimals normalised to 2 places (`xsd:decimal`). 5,140 of 7,058 rows kept.
- **D1:** rows without Food or Group dropped; plurals folded (almonds -> almond); allergen keys matched from the food name first, then from the Allergy label; Group -> Type -> Class chain linked with `partOfCategory`. Labels that are not food allergens are skipped (added in Iteration 2).
- **D2:** one `nr:Dish` per product (259 dishes); ingredients from Main Ingredient / Sweetener / Fat-Oil / Seasoning; an ingredient reuses the USDA food node when the match is unique, otherwise a new `ing:` node (averaged nutrients if several USDA matches); allergens not explained by any ingredient are asserted on the dish.
- **D4:** five rules -> `nr:DietaryRule` nodes with threshold, action and guideline source.

## A4. URI design
- **Vocabulary (T-Box, hash namespace):** `http://example.org/nutrireason#` (prefix `nr:`), e.g. `nr:unsafeFor`, `nr:Hypertension`.
- **Instances (A-Box, slash namespace):** `http://example.org/nutrireason/resource/<kind>/<slug>` with kinds `food, dish, ingredient, group, type, class, allergen, rule`.
- **Slug:** lower-case ASCII with underscores (`Almond Cookies` -> `dish/almond_cookies`). Slugs are readable, stable and have no spaces. Schema and data are kept apart, and the same label in different kinds never clashes (`group/dairy` vs `type/dairy`).

## A5. Incomplete work at the Iteration 1 deadline
- Non-allergen labels from D1 were still in the graph (fixed in Iteration 2, see B2).
- `GlutenAllergen` was not linked to any condition and this was not documented (documented in Iteration 2).

## A6. Issues faced
- The D1 `Allergy` column also contains labels that are not food allergens (Sugar, Insulin, Thyroid, Ochratoxin, Aquagenic Urticaria, Hypersensitivity). In Iteration 1 they became `nr:Allergen` nodes and showed up in CQ11. **Fixed in Iteration 2** (see B2).
- D1 groups some poultry under "Offal"; the group label is taken as given.
- OWL is open-world: "safe" is implemented with `FILTER NOT EXISTS` and only trusted for foods that have a D1 group (CQ3, CQ10).
- GraphDB does not run SWRL, so R1-R5 are re-implemented as SPARQL INSERT rules.
- R5 makes every dish with table salt unsafe for hypertension (salt has 38,758 mg sodium per 100 g, although dishes use little of it), so CQ6 is dominated by salt.

## A7. Iteration 1 member contributions
| Member | GitHub | Tasks | Deliverables | Representative commits |
|---|---|---|---|---|
| Muhammad Zamin | `zamin-muhammad` | Finalised the 14 competency questions and checked category coverage (multi-hop, inference, aggregation/filtering, LLM-difficult); prepared the CQ-to-KG mapping table; coordinated with Romaisa and Maham so every CQ is answerable from the KG; dataset selection | Competency_Questions.pdf, CQ_to_KG_Mapping.pdf | (submitted as PDFs, not committed) |
| Romaisa | `Ru-1234` | Ontology design in Protege (classes, object/datatype properties, domain/range, subclasses, T-Box/A-Box split, reasoning constructs RC1-RC6); data cleaning; RDF transformation (`build_kg.py`); URI design | `nutrireason_tbox.ttl`, `abox.ttl`, cleaned datasets, `DATA_PIPELINE.md` (transformation + URI design) | `35d482f` datasets + build_kg.py; `2023cff` ontology + A-Box; `f2babb7` report docs + Protege screenshots; `4983e0e` plural-stripping fix, nut keywords, rule order; `e78fb1e` README |
| Maham Anjum | `mahamanjum99` | GraphDB repository, import and 500+ triple check, graph visualisation; 14 SPARQL queries covering all required features; 3 symbolic inference examples (explicit facts -> rule -> inferred fact) | GraphDB screenshots, visualisation, `.rq` queries, query results, `INFERENCE_EXAMPLES.md` | `5d31592` SPARQL CQ1-CQ14 + inference demos; `97edcb2` GraphDB results, inference screenshots, visual graph |

---

# PART B - ITERATION 2 (Modern KG Reasoning & KG-Grounded LLM) - status on 20 Nov

## B1. Planned work division
| Member | Assigned part |
|---|---|
| Romaisa | Modern KG reasoning (Option A: link prediction with KG embeddings) + Iteration 1 fixes |
| Maham | KG retrieval layer (entity linking, SPARQL templates, explicit/inferred tags, insufficient-evidence detection) |
| Zamin | LLM application + UI + 10-CQ evaluation + explainability examples |

## B2. Completed so far
**Iteration 1 fixes (Romaisa, 20 Nov):**
- `build_kg.py` now skips D1 labels that are not food allergens (`NON_ALLERGEN_LABELS`: Sugar, Insulin, Thyroid, Ochratoxin, Aquagenic Urticaria, Hypersensitivity, and a bare "Allergy"). This affected 18 D1 foods and removed 64 incorrect inferred triples (7,673 -> 7,609).
- Fixed a naming bug that shortened "Oral Allergy Syndrome" to "Oral Syndrome", and could create an empty allergen URI from a bare "Allergy" label.
- Documented in the T-Box why `GlutenAllergen` triggers no condition (scope is four conditions; D4 has no gluten rule).
- Rebuilt `abox.ttl` (42,027 triples) and `inferred.ttl`, re-ran all 18 queries, and updated `README.md`, `DATA_PIPELINE.md`, `INFERENCE_EXAMPLES.md` and this report. CQ11 now lists only real allergens (Dairy 137, Wheat/Gluten 59, Chicken 44, ...).

**First working version of the full pipeline (committed by Zamin, 20 Nov):**
- `reasoning/materialize.py` keeps rule-inferred triples in a separate `inferred.ttl`. `reasoning/link_prediction.py` runs TransE and RotatE (PyKEEN) against a popularity baseline: Exp 1 hides 15% of `containsAllergen` links on the explicit graph; Exp 2 hides 15% of `unsafeFor` links on the materialised graph. Predictions are labelled "PREDICTION (not a fact)".
- `retrieval/retriever.py`: entity linking, SPARQL templates, explicit/inferred tags, insufficient-evidence flag.
- `app/llm.py` (Groq, `openai/gpt-oss-120b`, temperature 0) and `app/streamlit_app.py`.
- `evaluation/run_eval.py`, `unseen_check.py`, `explainability.py`, `manual_review.md`, and the report builder.

**Results so far (computed before the 20 Nov KG fix; must be re-run):**
| Experiment | Model | MRR | Hits@1 | Hits@10 |
|---|---|---|---|---|
| Exp 1 `containsAllergen` (explicit) | RotatE | 0.602 | 0.312 | 0.972 |
| | TransE | 0.303 | 0.047 | 0.755 |
| | Popularity baseline | 0.374 | 0.228 | 0.710 |
| Exp 2 `unsafeFor` (materialised) | RotatE | 0.566 | 0.240 | 1.000 |
| | TransE | 0.521 | 0.145 | 0.943 |
| | Popularity baseline | 0.731 | 0.510 | 1.000 |

10-CQ evaluation: LLM only 0/10 correct, KG-grounded 10/10. Answers with unsupported claims: 9/10 vs 1/10. This is a development-set score, because the same CQs were used to debug the retriever (see `evaluation/manual_review.md`).

## B3. Known issues
- **Exp 2:** the popularity baseline beats both embedding models (MRR 0.731 vs 0.566). `unsafeFor` has only 4 possible tails, and its links are produced by the rules from other facts, so the task is partly circular. This needs analysis or a redesign.
- **TransE Hits@1 = 0.047 in Exp 1:** TransE struggles with many-to-one relations (many foods -> one allergen). RotatE handles these better.
- **Stale numbers:** the evaluation, link prediction metrics and report PDF were produced before the KG fix. For example, the CQ11 expected answer still lists "Sugar 62". All of these must be regenerated.
- **Workload:** the first versions of all three Iteration 2 components were committed from one account in a single session. Each member is taking ownership of their assigned part and committing their own improvements before the deadline (brief §6.2, §7).

## B4. Remaining work (to 29 Nov)
| Task | Owner | Status |
|---|---|---|
| Re-run `link_prediction.py` on the fixed KG; update metrics and predictions | Romaisa | Pending |
| Analyse/redesign Exp 2; add a third model (DistMult/ComplEx) and/or a real KG-completion experiment with manual plausibility check | Romaisa | Pending |
| Write the "Modern KG reasoning" report section with citations (Bordes et al. 2013 TransE; Sun et al. 2019 RotatE; PyKEEN docs) | Romaisa | Pending |
| Review, improve and own the retrieval layer; write the retrieval report section | Maham | Pending (starting 21-22 Nov) |
| Re-run the 10-CQ evaluation and explainability examples on the fixed KG; update the comparison table | Zamin | Pending |
| Reload GraphDB with the updated T-Box/A-Box and rules; fresh screenshots | Maham | Pending |
| 3-5 minute demo video (stored externally) | All | Pending |
| Final consolidated PDF, contribution table with commit links, final commit hash, instructor repo access | All | Pending |

## B5. Iteration 2 member contributions (so far)
| Member | GitHub | Work done | Representative commits |
|---|---|---|---|
| Romaisa | `Ru-1234` | Iteration 1 KG fixes (non-allergen labels, naming bug, gluten scope); rebuilt KG and inferred graph; re-ran queries; updated docs and this report | (hash to be added after push) |
| Muhammad Zamin | `zamin-muhammad` | First version of the link prediction, retrieval, LLM app, evaluation and report builder (AI-assisted) | `928916c` link prediction + materialisation; `10ce4f4` retrieval layer; `1f5e592` LLM client + Streamlit app; `1fc1f50` 10-CQ evaluation + explainability; `fa870c4` README + report builder; `bd724ea` report PDF |
| Maham | `mahamanjum99` | Retrieval layer ownership and improvements | - |
