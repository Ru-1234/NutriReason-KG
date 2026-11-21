# Link prediction (Option A): how `reasoning/link_prediction.py` works

Author: Romaisa (Ru-1234). Draft of report Section 6.

## 1. The task in one sentence

A knowledge graph is never complete. Link prediction learns a vector (an *embedding*) for every entity
and relation, then gives every possible triple `(head, relation, tail)` a score. A high score means "this
link is probably true". We test it by hiding some real links and checking whether the model ranks them
near the top.

We ask tail questions only: `(food, nr:containsAllergen, ?)` and `(food, nr:unsafeFor, ?)`.

## 2. The two experiments

| | Exp 1 | Exp 2 |
|---|---|---|
| Graph | T-Box + A-Box (explicit facts only) | T-Box + A-Box + `inferred.ttl` (rule output) |
| Relation hidden | `nr:containsAllergen` (991 links, 45 allergens) | `nr:unsafeFor` (2,071 links, 4 conditions) |
| Test links (15%) | 148 | 310 |

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
  relations, and in our runs it fits the many-to-one structure much better (Exp 1 MRR 0.612 vs 0.315).
  Honest caveat: RotatE also uses a stronger loss (self-adversarial sampling), so part of the gap may come
  from the training setup and not only from the model.

## 5. Bug B1, and why the old samples looked broken

The old sample predictions ranked *all* entities, so a food could be "predicted" as its own allergen,
or as a food group or a class ("Chronic disease", `owl:NamedIndividual`). The repeated scores
(-13.424 in Exp 1, -13.921 in Exp 2) have a simple cause. In TransE, putting the head itself as the
tail gives score −‖h + r − h‖ = −‖r‖. That number is the same for every food. So the head came out on
top whenever the model was unsure. The fix keeps only type-correct tails, never the head itself, and
never links already in training.

## 6. Labels and limits

- Every predicted row is marked `PREDICTION (not a fact)` and is never added to the KG or used by the
  retriever.
- Numbers are a mean over 3 seeds. With 148 and 310 test links, differences of about 0.02 MRR are
  within noise.
- Numeric data (sugar, sodium) is invisible to these models, because literals are dropped in `load()`.

References: Bordes et al. (2013), *Translating Embeddings for Modeling Multi-relational Data*, NeurIPS;
Sun et al. (2019), *RotatE: Knowledge Graph Embedding by Relational Rotation in Complex Space*, ICLR;
Ali et al. (2021), *PyKEEN 1.0*, JMLR; Rossi et al. (2021), *Knowledge Graph Embedding for Link
Prediction: A Comparative Analysis*, ACM TKDD.
