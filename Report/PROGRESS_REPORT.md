# NutriReason - Iteration 1 Progress Report
Team: krr-08-nutrireason | Course: AI-3001 KRR | Submission: 15 November 2026

## 1. Completed work
- 14 competency questions + CQ-to-KG mapping (Report/ or root PDF).
- Ontology (T-Box): 12 core classes (+ allergen / condition subclasses and 3 inferred classes), 10 object properties, 5 datatype properties, constructs RC1-RC6 (subclass, hasValue, transitive, inverse, property chain, rules R1-R4 + R5). File: Ontology/nutrireason_tbox.ttl, viewed in Protege.
- A-Box built by `build_kg.py` from D1-D4 (see section 3). File: RDF_Knowledge_Graph/abox.ttl. Total triples loaded in GraphDB: ____ (fill in from GraphDB).
- Graph loaded in GraphDB repository `nutrireason`; visual graph screenshot in Visualization/.
- Rules script `rules_graphdb.ru` (SPARQL equivalents of R1-R5) run in GraphDB: +____ inferred triples (offline check: +7,673).
- 14 SPARQL queries (CQ1-CQ14) + 3 inference demos (INF1-INF3) + sanity query; outputs in Results/.

## 2. SPARQL feature coverage
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

## 3. Data cleaning / transformation (build_kg.py)
- All CSVs read as text, headers and cells trimmed, whitespace collapsed, exact duplicate rows dropped.
- D3 (USDA): rows with missing or negative Calories/Sodium/Sugar removed; duplicate IDs and duplicate names removed; decimals normalised to 2 places (xsd:decimal).
- D1: rows without Food or Group dropped; plurals folded (almonds -> almond); allergen keys matched from the food name first, then from the Allergy label; Group -> Type -> Class chain linked with `partOfCategory`.
- D2: one `nr:Dish` per product; ingredients from Main Ingredient / Sweetener / Fat-Oil / Seasoning; an ingredient reuses the USDA food node when the match is unique, otherwise a new `ing:` node (averaged nutrients if several USDA matches); allergens not explained by any ingredient are asserted on the dish.
- D4: five rules -> `nr:DietaryRule` nodes with threshold, action and guideline source.

## 4. URI design
- Vocabulary (T-Box, hash namespace): `http://example.org/nutrireason#` (prefix `nr:`) e.g. `nr:unsafeFor`, `nr:Hypertension`.
- Instances (A-Box, slash namespace): `http://example.org/nutrireason/resource/<kind>/<slug>` with kinds `food, dish, ingredient, group, type, class, allergen, rule`.
- Slug = lower-case ASCII, underscores (`Almond Cookies` -> `dish/almond_cookies`). Readable, stable, no spaces; schema and data are kept apart; the same label in different kinds never clashes (`group/dairy` vs `type/dairy`).

## 5. Incomplete work / next steps
(write honestly, e.g. fill from your own list)

## 6. Issues faced
- D1 `Allergy` column also contains non-allergen labels (Sugar, Insulin, Oral Syndrome, Allium); they became `nr:Allergen` nodes, so they show up in CQ11.
- D1 groups some poultry under "Offal"; the group label is taken as given.
- OWL is open-world: "safe" is implemented with FILTER NOT EXISTS and only trusted for foods that have a D1 group (CQ3, CQ10).
- GraphDB does not run SWRL, so R1-R5 are re-implemented as SPARQL INSERT rules.
- R5 makes every dish with table salt unsafe for hypertension (CQ6 is dominated by salt).

## 7. Member contributions
| Member | ID | Contribution |
|---|---|---|
|  |  |  |
