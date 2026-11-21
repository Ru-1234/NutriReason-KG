# Link prediction (Option A): how `reasoning/link_prediction.py` works

Author: Romaisa (Ru-1234). Draft of report Section 6.

## 1. The task in one sentence

A knowledge graph is never complete. Link prediction learns a vector (an *embedding*) for every entity
and relation, then gives every possible triple `(head, relation, tail)` a score. A high score means "this
link is probably true". We test it by hiding some real links and checking whether the model ranks them
near the top.

We ask tail questions only: `(food, nr:containsAllergen, ?)` and `(food, nr:unsafeFor, ?)`.

## 2. The experiments

| | Exp 1 | Exp 2 |
|---|---|---|
| Graph | T-Box + A-Box (explicit facts only) | T-Box + A-Box + `inferred.ttl` (rule output) |
| Relation hidden | `nr:containsAllergen` (991 links, 45 allergens) | `nr:unsafeFor` (2,071 links, 4 conditions) |
| Test links (15%) | 148 | 310 |
| Training graph | 8,892 entity-entity triples | 16,501 entity-entity triples |
| Random-guess MRR (type-constrained) | 0.098 | 0.544 |

Both graphs have 5,871 entities. Experiment 3 (section 8) uses the Exp 1 graph with nothing hidden
and suggests allergens for foods that have none.

## 3. The functions, in order

**`load(include_inferred)`** reads the Turtle files with rdflib and keeps only triples where both
subject and object are URIs and the subject is in our namespace. Literals (sugar, sodium, calories,
labels) are dropped, because TransE and RotatE only work on entity-to-entity links. `rdf:type` becomes
the relation `type`, `rdfs:subClassOf` stays, and `nr:` properties are kept. It also returns a label
dictionary so the output CSV shows "Dairy" instead of a URI.

**`short(u, labels)`** turns a URI into its label (or the last part of the URI) for printing.

**`split(triples, rel, frac, seed)`** shuffles the links of the target relation (fixed seed, so it can be
repeated) and moves 15% of them to the test set. A link is only moved if both its head and its tail
still have at least one other triple, so every test entity still appears in training. Without this, the
model would have a random, never-trained vector for that entity. All other relations stay in training.

**`candidate_tails(triples, rel)`** (added for bug B1) lists the entities that may be a tail of the
relation: instances of its `rdfs:range` class or a subclass. That is the 45 allergens for
`containsAllergen` and the 4 health conditions for `unsafeFor`.

**Training (inside `run_experiment`)** uses PyKEEN's `pipeline` for each model and seed: 100-dimensional
embeddings, 200 epochs, Adam, batch 512, sLCWA training with 32 negative examples per true triple
(made by replacing the head or tail with a random entity). The loss pushes true triples above the fake
ones. TransE uses PyKEEN's default margin ranking loss (lr 0.01). RotatE uses the self-adversarial
negative sampling loss from the RotatE paper (margin 9, lr 0.005).

**`filtered_tail_ranks(model, tf, test, all_true, cand=None)`** scores each test pair `(h, r)` against
every entity. The rank of the true tail is 1 + the number of entities with a strictly higher score.
*Filtered* means other tails that are also true for the same `(h, r)` are removed first. For example,
if a cheese contains Dairy and we are testing Wheat, Dairy is not counted as a mistake. With `cand`,
only type-correct entities compete (the *type-constrained* rank).

**`baseline_ranks(train, test, rel, tf, cand=None)`** is the popularity baseline. It ignores the head
and ranks tails by how often they appear as tails of the relation in training (Dairy first, then Chicken,
...). Ties get the expected rank under random tie-breaking. Only real allergens/conditions have a count
above 0, so this baseline is already type-constrained in practice.

**`metrics(ranks)`** turns ranks into scores:
- **MRR** (mean reciprocal rank) is the mean of 1/rank. Rank 1 gives 1, rank 2 gives 0.5, rank 4
  gives 0.25. Higher is better, and the maximum is 1.
- **Hits@k** is the share of test links whose true tail is in the top k.
- **MR** (mean rank) is computed but not reported, because a few very bad ranks dominate it.

Example: ranks 1, 2 and 10 give MRR = (1 + 0.5 + 0.1) / 3 = 0.533, Hits@1 = 1/3 and Hits@10 = 3/3.

**`run_experiment(name, rel, include_inferred)`** puts it together. It loads the graph, then for each
seed it splits, trains TransE and RotatE, and scores them and the baseline. It then writes sample
predictions from the seed-0 models and returns the mean and standard deviation over the seeds (3 by
default). The main block runs both experiments and writes `metrics.json` and `metrics.md`.

## 4. TransE vs RotatE

- **TransE** (Bordes et al., 2013): a relation is a translation, `h + r ≈ t`.
  Score = −‖h + r − t‖. Weakness: if many foods have the same allergen (many-to-one), all their vectors
  are pushed toward `t − r`. If one food has several allergens (one-to-many), those allergen vectors
  are pushed toward the same point. So TransE cannot tell them apart well. This matches its low
  Hits@1 in Exp 1 (0.059).
- **RotatE** (Sun et al., 2019): embeddings are complex vectors and a relation is a rotation, `h ∘ r ≈ t`
  with |rᵢ| = 1. Score = −‖h ∘ r − t‖. Rotations can model symmetric, antisymmetric, inverse and composed
  relations, and in our runs it fits the many-to-one structure much better (Exp 1 MRR 0.612 vs 0.315;
  type-constrained 0.852 vs 0.618).
  Honest caveat: RotatE also uses a stronger loss (self-adversarial sampling), so part of the gap may come
  from the training setup and not only from the model.

## 5. Bug B1, and why the old samples looked broken

The old sample predictions ranked *all* entities, so a food could be "predicted" as its own allergen,
or as a food group or a class ("Chronic disease", `owl:NamedIndividual`). The repeated scores
(-13.424 in Exp 1, -13.921 in Exp 2) have a simple cause. In TransE, putting the head itself as the
tail gives score −‖h + r − h‖ = −‖r‖. That number is the same for every food. So the head came out on
top whenever the model was unsure. The fix keeps only type-correct tails, never the head itself, and
never links already in training.

Result after the fix (`reasoning/results/predictions_*.csv`, seed-0 models, 20 test foods per model):

| | Exp 1 hidden link at rank 1 | Exp 1 in top 3 | Exp 2 hidden link at rank 1 | Exp 2 in top 3 |
|---|---|---|---|---|
| RotatE | 16 / 20 | 20 / 20 | 19 / 20 | 20 / 20 |
| TransE | 12 / 20 | 12 / 20 | 17 / 20 | 20 / 20 |

No row predicts the head itself, and every predicted tail is an allergen (Exp 1) or one of the 4
conditions (Exp 2). Example: for "Cheese, Feta", TransE's old top answer was the food itself
(−13.424). Now it is Dairy (−13.915), the hidden link, with the same score as before. RotatE's
wrong rank-1 answers are often close relatives of the right one: Seed instead of Pecan for pecans,
Chicken instead of Poultry for turkey, and Peanut instead of Soy / Legume for lima beans.

## 6. Labels and limits

- Every predicted row is marked `PREDICTION (not a fact)` and is never added to the KG or used by the
  retriever.
- Numbers are a mean over 3 seeds. With 148 and 310 test links, differences of about 0.02 MRR are
  within noise.
- Numeric data (sugar, sodium) is invisible to these models, because literals are dropped in `load()`.

## 7. Experiment 2: why it seemed to lose to the baseline, and why the fair result is not a win either

| Model | MRR (all entities) | MRR (type-constrained, 4 candidates) | Hits@1 (type-constrained) |
|---|---|---|---|
| Popularity baseline | **0.731 ± 0.015** | 0.731 ± 0.015 | 0.510 |
| RotatE | 0.662 ± 0.037 | **0.994 ± 0.006** | 0.989 |
| TransE | 0.535 ± 0.027 | 0.959 ± 0.008 | 0.927 |
| Random guess among the 4 conditions | – | 0.544 | – |

The counts below come from `python reasoning/exp2_analysis.py`.

**1. The original comparison was not equal.** The baseline only gives a count above 0 to the 4
conditions, so it effectively ranks among 4 candidates (its Hits@10 = 1.0 is automatic). TransE and
RotatE ranked the true condition among all 5,871 entities, so any food, class or `owl:NamedIndividual`
that scored slightly higher lowered their MRR. When all three rank the same 4 conditions, both models
clearly beat the baseline (RotatE 0.994 vs 0.731). The same thing happens in Exp 1: RotatE goes from
0.612 to 0.852 type-constrained, while the baseline stays at 0.420.

**2. The baseline has little to work with: 4 tails, skewed counts.** Of the 2,071 `unsafeFor` links,
Hypertension has 945 (45.6%), Type 2 diabetes 745 (36.0%), Lactose intolerance 342 (16.5%) and
Nut allergy 39 (1.9%). Always answering "Hypertension, then Type 2 diabetes" gives Hits@1 ≈ 0.51, and
random guessing among the 4 already gives MRR 0.544.

**3. But a near-perfect score here is not evidence of learning, because the task is circular.**
None of the 2,071 links is stated in the data. Every one was produced by our own rules
(`rules_graphdb.ru`), and every one is explained by another triple in the same graph:

| Condition | Explained by | Links |
|---|---|---|
| Hypertension | `food a nr:HighSodiumFood` (R3) | 902 |
| Hypertension | an ingredient that is unsafe (R5) | 43 |
| Type 2 diabetes | `food a nr:HighSugarFood` (R2) | 669 |
| Type 2 diabetes | an ingredient that is unsafe (R5) | 76 |
| Lactose intolerance | `containsAllergen` Dairy → `triggers` (R1) | 342 |
| Nut allergy | `containsAllergen` nut allergen → `triggers` (R1) | 39 |

When an `unsafeFor` link is hidden, the matching `HighSugarFood`/`HighSodiumFood` type triple stays in
training. That is 1,571 links (76%). So the model only has to learn "HighSugarFood → Type 2 diabetes",
a rule we wrote ourselves. That is why RotatE reaches 0.994. The SPARQL rule already gets these links
100% right, and it can say why.

**4. The real evidence is numeric, and embeddings cannot see numbers.** R2 and R3 fire on
`sugarPer100g > 22.5` and `sodiumPer100g > 600`. `load()` drops these literals, so the models only see
the class-type shadow of the threshold. They never see the threshold itself.

**Conclusion.** Exp 2 "lost" only because of an unequal evaluation. Under a fair, type-constrained
evaluation it is almost perfect, but only because the answers leak through rule-generated triples. Either
way it does not show that embeddings find new knowledge. For `unsafeFor`, symbolic rules are the right
tool: they are exact, explainable and auditable, which matters for a health-safety answer. Embeddings
are useful where the graph is really incomplete and no rule can fill the gap, as in Exp 1
(`containsAllergen`, explicit data only, no leak), where RotatE beats the baseline both ways
(0.612 vs 0.420; type-constrained 0.852 vs 0.420). Experiment 3 therefore uses embeddings to *suggest*
missing allergens and labels them as predictions, never as facts.

A possible redesign (not done, for lack of time): remove the `HighSugarFood`/`HighSodiumFood` type
triples and the R5 links from training, and evaluate only on dishes. That would test whether the model can
generalise beyond copying the rules.

## 8. Experiment 3: real KG completion (suggesting allergens for foods that have none)

Script: `reasoning/exp3_completion.py`. Outputs: `reasoning/results/predictions_exp3_completion.csv`
(top 3 for every target food) and `reasoning/results/exp3_top10_manual_check.csv` (manual check).

**Setup.** RotatE (same settings as Exp 1) is trained on the whole explicit graph with nothing hidden.
There are 3 seeds, and their scores are averaged. Of 5,702 foods, 4,560 have no allergen at all,
neither stated nor inferred by rule RC5. Only **289** of these have any other link: a food group,
ingredients, or a dish that uses them. The other 4,271 are USDA foods that the graph only describes
as "a Food", so the model has nothing to learn about them. We therefore predict only for the 289.
For each, the 45 allergens are ranked (type-constrained, as in the B1 fix).

**Confidence.** The model gives the *known* allergen links a median score of −7.01 (10th–90th
percentile −7.88 to −5.76). The best new prediction scores −8.92, and **none of the 289 top-1
predictions reaches the median known link**. So every prediction is a weak suggestion, not something
the model is as sure about as a stored fact.

**Manual check of the 10 most confident predictions** (each food's top-1 allergen; checked by hand
against the food's plant family and the KG's own data for that group):

| # | Food | Predicted allergen | Group in the KG | Check | Reason |
|---|---|---|---|---|---|
| 1 | Radish root | Cruciferous | Cruciferous vegetable | plausible | radish is a cruciferous (cabbage-family) vegetable |
| 2 | Artichokes, raw | Ltp | Composite vegetable | unsure | same plant family as lettuce (LTP in the KG), but LTP cross-reactivity is not guaranteed |
| 3 | Chicory | Ltp | Composite vegetable | unsure | same reason as artichoke |
| 4 | Watercress, raw | Cruciferous | Cruciferous vegetable | plausible | watercress is a cruciferous vegetable |
| 5 | Artichokes, cooked | Ltp | Composite vegetable | unsure | same food as #2, cooked |
| 6 | Salsify, cooked | Ltp | Composite vegetable | unsure | same reason as artichoke |
| 7 | Shungiku | Ltp | Composite vegetable | unsure | same reason as artichoke |
| 8 | Artichokes, frozen, cooked | Ltp | Composite vegetable | unsure | same food as #2, frozen |
| 9 | Japanese persimmon | Banana | Tropical fruit | not plausible | a persimmon is not a banana; most tropical fruits in the KG are linked to Oral Allergy Syndrome, not Banana |
| 10 | Turnip root | Cruciferous | Cruciferous vegetable | plausible | turnip is a cruciferous vegetable |

Result: **3 plausible, 6 unsure, 1 not plausible**.

**What the model learned.** Every top-10 prediction is a *group analogy*. In the KG, 37 of the 47
"Cruciferous vegetable" foods that have an allergen are linked to Cruciferous, so new cruciferous
vegetables get Cruciferous. In "Composite vegetable", the only allergen links are LTP on 6 lettuce
entries (plus Ragweed on burdock), so the model passes lettuce's LTP to artichoke, chicory, salsify and
shungiku. This is reasonable at family level, but it is a guess about a specific protein. The 3
artichoke rows are really one food in 3 preparations, so the top 10 covers only 8 different foods.
Across all 289 targets, the most frequent top-1 prediction is Dairy (119 foods, 41%). Dairy is also
the most common allergen in the KG (221 links), so this is probably popularity bias for foods with few
links, not real evidence.

**Conclusion.** Link prediction can produce useful *candidates* for missing allergen links, mainly
when a food shares a group with well-labelled foods. Its confidence is lower than for known facts, and
1 of the top 10 is clearly wrong. That is why predictions are labelled `PREDICTION (not a fact)`, are
never added to the KG, and are never used by the retriever or the LLM. A domain expert would have to
confirm each one before it could become a fact.

## References

Bordes et al. (2013), *Translating Embeddings for Modeling Multi-relational Data*, NeurIPS;
Sun et al. (2019), *RotatE: Knowledge Graph Embedding by Relational Rotation in Complex Space*, ICLR;
Ali et al. (2021), *PyKEEN 1.0*, JMLR; Rossi et al. (2021), *Knowledge Graph Embedding for Link
Prediction: A Comparative Analysis*, ACM TKDD.
