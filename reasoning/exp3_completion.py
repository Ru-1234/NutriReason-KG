#!/usr/bin/env python3
"""Experiment 3 - real KG completion: suggest allergens for foods that have none.

1. Train RotatE (same settings as Exp 1) on the WHOLE explicit graph (T-Box + A-Box), nothing hidden.
   One model per seed. The scores of the seeds are averaged.
2. Target foods: food / dish / ingredient instances with no nr:containsAllergen link, neither stated
   (abox.ttl) nor inferred (inferred.ttl, rule RC5). They must also have at least one other link (a food
   group, an ingredient, a dish that uses them). Foods with only "rdf:type Food" give the model nothing
   to learn from, so their predictions would be noise.
3. For each target food, rank the 45 allergens (type-constrained, as in the B1 fix).
   Reference point: the median score the model gives to the KNOWN containsAllergen links.
4. Outputs (reasoning/results/), every row labelled PREDICTION (not a fact). Never loaded into the KG:
   predictions_exp3_completion.csv   top-3 allergens for every target food
   exp3_top10_manual_check.csv       the 10 most confident foods (top-1 allergen each), with empty
                                     columns manual_check / reason to fill in by hand

Usage (repo root):  python reasoning/exp3_completion.py [--epochs 200] [--dim 100] [--seeds 3]
"""
import argparse, os
import numpy as np, pandas as pd, torch
from rdflib import Graph, URIRef, RDF, RDFS
from pykeen.pipeline import pipeline
from pykeen.triples import TriplesFactory

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
NR = "http://example.org/nutrireason#"
REL = "nr:containsAllergen"
OUT = P("reasoning", "results")
os.makedirs(OUT, exist_ok=True)

ap = argparse.ArgumentParser()
ap.add_argument("--epochs", type=int, default=200)
ap.add_argument("--dim", type=int, default=100)
ap.add_argument("--seeds", type=int, default=3)
args = ap.parse_args()


def load(files):
    """Same filtering as link_prediction.py load(): entity-entity triples only."""
    g = Graph()
    for f in files:
        g.parse(P(*f))
    labels = {str(s): str(o) for s, o in g.subject_objects(RDFS.label)}
    trip = set()
    for s, p, o in g:
        if isinstance(s, URIRef) and isinstance(o, URIRef) and str(s).startswith("http://example.org/nutrireason"):
            if p == RDF.type:
                trip.add((str(s), "type", str(o)))
            elif p == RDFS.subClassOf:
                trip.add((str(s), "rdfs:subClassOf", str(o)))
            elif str(p).startswith(NR):
                trip.add((str(s), str(p).replace(NR, "nr:"), str(o)))
    return sorted(trip), labels


def instances_of(triples, root):
    """Instances of `root` or any of its subclasses."""
    sub = {}
    for s, p, o in triples:
        if p == "rdfs:subClassOf":
            sub.setdefault(o, set()).add(s)
    classes, stack = {root}, [root]
    while stack:
        for c in sub.get(stack.pop(), ()):
            if c not in classes:
                classes.add(c)
                stack.append(c)
    return {s for s, p, o in triples if p == "type" and o in classes}


triples, labels = load([("Ontology", "nutrireason_tbox.ttl"), ("RDF_Knowledge_Graph", "abox.ttl")])
inferred, _ = load([("RDF_Knowledge_Graph", "inferred.ttl")])
name = lambda u: labels.get(u, u.rsplit("/", 1)[-1])

allergens = sorted(instances_of(triples, NR + "Allergen") | {t for _, r, t in triples if r == REL})
foods = instances_of(triples, NR + "Food")
has_allergen = {h for h, r, _ in triples + inferred if r == REL}
linked = {x for h, r, t in triples if r not in ("type", "rdfs:subClassOf") for x in (h, t)}
targets = sorted((foods - has_allergen) & linked)
print(f"{len(foods)} foods, {len(foods - has_allergen)} without any allergen, "
      f"{len(targets)} of them have another link -> targets; {len(allergens)} candidate allergens", flush=True)

# context for the manual check: food group, ingredients of a dish, dishes that use an ingredient
ctx = {}
for h, r, t in triples:
    if r == "nr:belongsToGroup":
        ctx.setdefault(h, []).append("group: " + name(t))
    elif r == "nr:hasIngredient":
        ctx.setdefault(h, []).append("ingredient: " + name(t))
        ctx.setdefault(t, []).append("used in: " + name(h))

tf = TriplesFactory.from_labeled_triples(np.array(triples, dtype=str))
ent, rid = tf.entity_to_id, tf.relation_to_id[REL]
a_ids = torch.tensor([ent[a] for a in allergens], dtype=torch.long)
known = [(h, t) for h, r, t in triples if r == REL]
small_test = TriplesFactory.from_labeled_triples(np.array(triples[:50], dtype=str),
                                                 entity_to_id=ent, relation_to_id=tf.relation_to_id)

target_scores = np.zeros((len(targets), len(allergens)))
known_scores = np.zeros(len(known))
for seed in range(args.seeds):
    r = pipeline(model="RotatE", training=tf, testing=small_test, random_seed=seed,
                 model_kwargs=dict(embedding_dim=args.dim),
                 optimizer="Adam", optimizer_kwargs=dict(lr=0.005),
                 loss="nssa", loss_kwargs=dict(margin=9.0, adversarial_temperature=1.0),
                 training_loop="slcwa", negative_sampler_kwargs=dict(num_negs_per_pos=32),
                 training_kwargs=dict(num_epochs=args.epochs, batch_size=512, use_tqdm=False),
                 evaluation_kwargs=dict(use_tqdm=False), device="cpu")
    model = r.model
    model.eval()
    with torch.no_grad():
        for i, h in enumerate(targets):
            sc = model.score_t(torch.tensor([[ent[h], rid]])).squeeze(0)
            target_scores[i] += np.asarray(sc[a_ids].tolist()) / args.seeds
        for j, (h, t) in enumerate(known):
            sc = model.score_t(torch.tensor([[ent[h], rid]])).squeeze(0)
            known_scores[j] += float(sc[ent[t]]) / args.seeds
    print(f"  seed {seed} trained", flush=True)

ref_median = float(np.median(known_scores))
print(f"Known containsAllergen links: median score {ref_median:.3f} "
      f"(10th-90th percentile {np.percentile(known_scores, 10):.3f} .. {np.percentile(known_scores, 90):.3f})")

rows = []
for i, h in enumerate(targets):
    order = np.argsort(-target_scores[i])[:3]
    for k, j in enumerate(order, 1):
        rows.append({"status": "PREDICTION (not a fact)", "food": name(h), "food_uri": h,
                     "context": "; ".join(sorted(set(ctx.get(h, []))))[:200],
                     "predicted_allergen": name(allergens[j]), "rank": k,
                     "score": round(float(target_scores[i, j]), 3),
                     "as_confident_as_median_known_link": bool(target_scores[i, j] >= ref_median)})
df = pd.DataFrame(rows)
df.to_csv(os.path.join(OUT, "predictions_exp3_completion.csv"), index=False)

top10 = df[df["rank"] == 1].sort_values("score", ascending=False).head(10).copy()
top10["manual_check"] = ""   # fill in by hand: plausible / not plausible / unsure
top10["reason"] = ""         # one short reason (e.g. "cheese -> Dairy", "no milk in a fruit")
top10.drop(columns=["food_uri", "rank"]).to_csv(os.path.join(OUT, "exp3_top10_manual_check.csv"), index=False)

print(f"\n{len(targets)} target foods; top-1 prediction as confident as the median known link: "
      f"{int(df[(df['rank'] == 1)]['as_confident_as_median_known_link'].sum())}")
print("Most predicted allergens (top-1):",
      df[df["rank"] == 1]["predicted_allergen"].value_counts().head(8).to_dict())
print("\nTop 10 for the manual check:")
for _, x in top10.iterrows():
    print(f"  {x['score']:8.3f}  {x['food'][:45]:45s} -> {x['predicted_allergen']:18s} | {x['context'][:60]}")
