#!/usr/bin/env python3
"""Option A - link prediction / KG completion with PyKEEN (TransE and RotatE).

Experiment 1 (explicit KG):   hide 15% of nr:containsAllergen links, train on the rest, recover them.
Experiment 2 (materialised):  hide 15% of nr:unsafeFor links (explicit + rule-inferred graph).

Metric: filtered tail-ranking (h, r, ?) -> Hits@1/3/10 and MRR, several random splits (mean +- std),
compared with a popularity baseline (rank tails by how often they occur as tail of that relation).
Each model is scored twice: against ALL entities (as before) and "type-constrained", i.e. only against
entities of the relation's range class (Allergen instances / the 4 HealthCondition instances).

Sample predictions are type-constrained too: a tail must belong to the range class and can never be
the head itself (bug B1: before this fix most top-1 "predictions" were the head food).

Outputs (reasoning/results/): metrics.json, metrics.md, predictions_<exp>.csv (labelled PREDICTION).

Usage (repo root):  python reasoning/link_prediction.py [--epochs 200] [--dim 100] [--seeds 3]
"""
import argparse, json, os, random
import numpy as np, pandas as pd, torch
from rdflib import Graph, URIRef, RDF, RDFS
from pykeen.pipeline import pipeline
from pykeen.triples import TriplesFactory

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
NR = "http://example.org/nutrireason#"
OUT = P("reasoning", "results")
os.makedirs(OUT, exist_ok=True)
# rdfs:range of each predicted relation in Ontology/nutrireason_tbox.ttl
RANGE_CLASS = {"nr:containsAllergen": NR + "Allergen", "nr:unsafeFor": NR + "HealthCondition"}

ap = argparse.ArgumentParser()
ap.add_argument("--epochs", type=int, default=200)
ap.add_argument("--dim", type=int, default=100)
ap.add_argument("--seeds", type=int, default=3)
ap.add_argument("--holdout", type=float, default=0.15)
args = ap.parse_args()


def load(include_inferred):
    g = Graph()
    g.parse(P("Ontology", "nutrireason_tbox.ttl"))
    g.parse(P("RDF_Knowledge_Graph", "abox.ttl"))
    if include_inferred:
        g.parse(P("RDF_Knowledge_Graph", "inferred.ttl"))
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


def short(u, labels):
    return labels.get(u, u.rsplit("/", 1)[-1].replace("#", ":"))


def split(triples, rel, frac, seed):
    rnd = random.Random(seed)
    cand = [t for t in triples if t[1] == rel]
    rnd.shuffle(cand)
    deg = {}
    for h, _, t in triples:
        deg[h] = deg.get(h, 0) + 1
        deg[t] = deg.get(t, 0) + 1
    test = []
    for t in cand:  # keep every entity connected in training
        if len(test) >= int(frac * len(cand)):
            break
        if deg[t[0]] > 1 and deg[t[2]] > 1:
            test.append(t)
            deg[t[0]] -= 1
            deg[t[2]] -= 1
    ts = set(test)
    return [t for t in triples if t not in ts], test


def candidate_tails(triples, rel):
    """Entities allowed as tail of `rel`: instances of its range class or of any subclass
    (e.g. alg:dairy is a nr:DairyAllergen, a subclass of nr:Allergen), plus every entity already
    seen as a tail of `rel`. Classes themselves (nr:ChronicDisease) and foods are excluded."""
    sub = {}
    for s, p, o in triples:
        if p == "rdfs:subClassOf":
            sub.setdefault(o, set()).add(s)
    classes, stack = {RANGE_CLASS[rel]}, [RANGE_CLASS[rel]]
    while stack:
        for c in sub.get(stack.pop(), ()):
            if c not in classes:
                classes.add(c)
                stack.append(c)
    cand = {s for s, p, o in triples if p == "type" and o in classes}
    cand |= {t for _, r, t in triples if r == rel}
    return sorted(cand)


def filtered_tail_ranks(model, tf, test, all_true, cand=None):
    """Filtered rank of the true tail among all entities (other known true tails are removed).
    If `cand` (list of entity URIs) is given, only those entities compete: type-constrained rank."""
    model.eval()
    ranks = []
    ent, rel = tf.entity_to_id, tf.relation_to_id
    known = {}
    for h, r, t in all_true:
        known.setdefault((h, r), set()).add(ent[t])
    cand_ids = None if cand is None else torch.tensor([ent[e] for e in cand], dtype=torch.long)
    with torch.no_grad():
        for h, r, t in test:
            sc = model.score_t(torch.tensor([[ent[h], rel[r]]])).squeeze(0).clone()
            true = ent[t]
            s_true = sc[true].item()
            if cand_ids is not None:
                keep = torch.zeros(sc.shape[0], dtype=torch.bool)
                keep[cand_ids] = True
                keep[true] = True
                sc[~keep] = -1e9
            for o in known[(h, r)]:
                if o != true:
                    sc[o] = -1e9
            ranks.append(int((sc > s_true).sum().item()) + 1)
    return ranks


def baseline_ranks(train, test, rel, tf, cand=None):
    cnt = {}
    for h, r, t in train:
        if r == rel:
            cnt[t] = cnt.get(t, 0) + 1
    ents = list(tf.entity_to_id) if cand is None else list(cand)
    known = {}
    for h, r, t in train + test:
        known.setdefault((h, r), set()).add(t)
    ranks = []
    for h, r, t in test:
        c = cnt.get(t, 0)
        better = sum(1 for e in ents if cnt.get(e, 0) > c and e not in known[(h, r)])
        ties = sum(1 for e in ents if cnt.get(e, 0) == c and e != t and e not in known[(h, r)])
        ranks.append(better + 1 + ties / 2.0)  # expected rank under random tie-breaking
    return ranks


def metrics(ranks):
    r = np.array(ranks, float)
    return {"MRR": float((1 / r).mean()), "Hits@1": float((r <= 1).mean()), "Hits@3": float((r <= 3).mean()),
            "Hits@10": float((r <= 10).mean()), "MR": float(r.mean()), "n_test": int(len(r))}


def run_experiment(name, rel, include_inferred):
    triples, labels = load(include_inferred)
    print(f"[{name}] {len(triples)} entity-entity triples, relation={rel}", flush=True)
    cand = candidate_tails(triples, rel)
    print(f"[{name}] {len(cand)} type-correct candidate tails for {rel}", flush=True)
    TC = " (type-constrained)"
    res = {m: [] for m in ["TransE", "RotatE", "Popularity baseline",
                           "TransE" + TC, "RotatE" + TC, "Popularity baseline" + TC]}
    seed0 = {}
    for seed in range(args.seeds):
        train, test = split(triples, rel, args.holdout, seed)
        tf_all = TriplesFactory.from_labeled_triples(np.array(triples, dtype=str))
        kw_f = dict(entity_to_id=tf_all.entity_to_id, relation_to_id=tf_all.relation_to_id)
        tf_tr = TriplesFactory.from_labeled_triples(np.array(train, dtype=str), **kw_f)
        tf_te = TriplesFactory.from_labeled_triples(np.array(test, dtype=str), **kw_f)
        res["Popularity baseline"].append(metrics(baseline_ranks(train, test, rel, tf_all)))
        res["Popularity baseline" + TC].append(metrics(baseline_ranks(train, test, rel, tf_all, cand)))
        for mname in ["TransE", "RotatE"]:
            kw = dict(model=mname, training=tf_tr, testing=tf_te, random_seed=seed,
                      model_kwargs=dict(embedding_dim=args.dim),
                      optimizer="Adam", optimizer_kwargs=dict(lr=0.01 if mname == "TransE" else 0.005),
                      training_loop="slcwa", negative_sampler_kwargs=dict(num_negs_per_pos=32),
                      training_kwargs=dict(num_epochs=args.epochs, batch_size=512, use_tqdm=False),
                      evaluation_kwargs=dict(use_tqdm=False), device="cpu")
            if mname == "RotatE":
                kw.update(loss="nssa", loss_kwargs=dict(margin=9.0, adversarial_temperature=1.0))
            r = pipeline(**kw)
            for key, cnd in [(mname, None), (mname + TC, cand)]:
                m = metrics(filtered_tail_ranks(r.model, tf_all, test, triples, cnd))
                res[key].append(m)
                print(f"  seed {seed} {key:26s} MRR={m['MRR']:.3f} H@1={m['Hits@1']:.3f} "
                      f"H@3={m['Hits@3']:.3f} H@10={m['Hits@10']:.3f}", flush=True)
            if seed == 0:
                seed0[mname] = r.model
                split0 = (tf_all, train, test)
    # sample predictions from the seed-0 models, type-constrained (fix for bug B1)
    tf_all, train, test = split0
    ent_by_id = {i: e for e, i in tf_all.entity_to_id.items()}
    train_set = set((h, t) for h, r, t in train if r == rel)
    test_set = set((h, t) for h, r, t in test)
    rid = tf_all.relation_to_id[rel]
    cand_ids = torch.tensor([tf_all.entity_to_id[e] for e in cand], dtype=torch.long)
    rows = []
    with torch.no_grad():
        for mname, model in seed0.items():
            model.eval()
            for h in list(dict.fromkeys(h for h, _, _ in test))[:20]:
                hid = tf_all.entity_to_id[h]
                sc = model.score_t(torch.tensor([[hid, rid]])).squeeze(0).clone()
                keep = torch.zeros(sc.shape[0], dtype=torch.bool)
                keep[cand_ids] = True          # only Allergen / HealthCondition instances
                keep[hid] = False              # a food is never its own allergen / condition
                for e in cand:                 # links already known from training are not new
                    if (h, e) in train_set:
                        keep[tf_all.entity_to_id[e]] = False
                if not keep.any():
                    continue
                sc[~keep] = float("-inf")
                top = torch.topk(sc, min(3, int(keep.sum())))
                for k, (v, i) in enumerate(zip(top.values, top.indices), 1):
                    t = ent_by_id[int(i)]
                    rows.append({"status": "PREDICTION (not a fact)", "model": mname, "head": short(h, labels),
                                 "relation": rel, "predicted_tail": short(t, labels), "rank": k,
                                 "score": round(float(v), 3), "recovers_held_out_link": (h, t) in test_set})
    pd.DataFrame(rows).to_csv(os.path.join(OUT, f"predictions_{name}.csv"), index=False)
    agg = {}
    for m, lst in res.items():
        agg[m] = {k: (float(np.mean([x[k] for x in lst])), float(np.std([x[k] for x in lst])))
                  for k in lst[0] if k != "n_test"}
        agg[m]["n_test"] = lst[0]["n_test"]
    return agg


out = {"config": vars(args)}
out["exp1_containsAllergen_explicit"] = run_experiment("exp1_containsAllergen", "nr:containsAllergen", False)
out["exp2_unsafeFor_materialised"] = run_experiment("exp2_unsafeFor", "nr:unsafeFor", True)
json.dump(out, open(os.path.join(OUT, "metrics.json"), "w"), indent=2)
with open(os.path.join(OUT, "metrics.md"), "w", encoding="utf-8") as f:
    for k, v in out.items():
        if k == "config":
            continue
        f.write(f"### {k}\n\n| Model | MRR | Hits@1 | Hits@3 | Hits@10 | n_test |\n|---|---|---|---|---|---|\n")
        for m, d in v.items():
            f.write(f"| {m} | " + " | ".join(f"{d[x][0]:.3f} ± {d[x][1]:.3f}" for x in ["MRR", "Hits@1", "Hits@3", "Hits@10"]) + f" | {d['n_test']} |\n")
        f.write("\n")
print(open(os.path.join(OUT, "metrics.md"), encoding="utf-8").read())
