#!/usr/bin/env python3
"""Why does Experiment 2 (nr:unsafeFor) lose to the popularity baseline?  Counts used in
Report/LINK_PREDICTION.md, section "Experiment 2 - an honest negative result".

For every nr:unsafeFor link in the materialised graph (abox + inferred) it finds which other
triple in the SAME graph already explains it (the rules in Ontology/rules_graphdb.ru):
  allergen path  food containsAllergen A, A triggers C                      (R1)
  class type     food a HighSugarFood -> Type2Diabetes, HighSodiumFood -> Hypertension (R2/R3)
  ingredient     dish hasIngredient I, I unsafeFor C                         (R5)
It also prints the MRR of random guessing among the type-correct tails (the floor for Exp 1 / Exp 2).

Usage (repo root):  python reasoning/exp2_analysis.py
"""
import os
from collections import Counter, defaultdict
from rdflib import Graph, URIRef, RDF, RDFS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
NR = "http://example.org/nutrireason#"
UNSAFE, CONTAINS, TRIGGERS, HAS_ING = (URIRef(NR + x) for x in
                                       ["unsafeFor", "containsAllergen", "triggers", "hasIngredient"])
T2D, HTN = URIRef(NR + "Type2Diabetes"), URIRef(NR + "Hypertension")
HIGH_SUGAR, HIGH_SODIUM = URIRef(NR + "HighSugarFood"), URIRef(NR + "HighSodiumFood")

g = Graph()
for f in [("Ontology", "nutrireason_tbox.ttl"), ("RDF_Knowledge_Graph", "abox.ttl"),
          ("RDF_Knowledge_Graph", "inferred.ttl")]:
    g.parse(P(*f))
label = {s: str(o) for s, o in g.subject_objects(RDFS.label)}
name = lambda u: label.get(u, str(u).rsplit("#", 1)[-1])

pairs = defaultdict(set)                       # (subject, predicate) -> objects
types = defaultdict(set)
for s, p, o in g:
    if isinstance(o, URIRef):
        pairs[(s, p)].add(o)
        if p == RDF.type:
            types[s].add(o)
unsafe = sorted((s, o) for s, p, o in g if p == UNSAFE)
explicit = Graph()                             # Exp 1 graph (no rule output)
explicit.parse(P("RDF_Knowledge_Graph", "abox.ttl"))
U = set(unsafe)


def explained_by(f, c):
    if any(c in pairs[(a, TRIGGERS)] for a in pairs[(f, CONTAINS)]):
        return "allergen path (R1)"
    if (c == T2D and HIGH_SUGAR in types[f]) or (c == HTN and HIGH_SODIUM in types[f]):
        return "class type (R2/R3)"
    if any((i, c) in U for i in pairs[(f, HAS_ING)]):
        return "ingredient (R5)"
    return "NOT explained"


print(f"nr:unsafeFor links: {len(unsafe)} "
      f"(stated in abox.ttl: {len(list(explicit.subject_objects(UNSAFE)))}, the rest come from the rules)")
print("\nBy condition:")
for c, n in Counter(name(c) for _, c in unsafe).most_common():
    print(f"  {c:22s} {n:5d}  ({n / len(unsafe):.1%})")
print("\nWhich triple in the same graph explains the link:")
for (c, why), n in sorted(Counter((name(c), explained_by(f, c)) for f, c in unsafe).items()):
    print(f"  {c:22s} {why:22s} {n:5d}")
per_head = Counter(Counter(f for f, _ in unsafe).values())
print("\nConditions per food:", dict(sorted(per_head.items())))


def random_mrr(links, n_cand):
    """Expected filtered MRR if the tail is picked at random among the type-correct candidates."""
    k = Counter(h for h, _ in links)
    tot = 0.0
    for h, _ in links:
        m = n_cand - (k[h] - 1)                # other true tails of h are filtered out
        tot += sum(1 / r for r in range(1, m + 1)) / m
    return tot / len(links)


allergens = {s for s, p, o in g if p == RDF.type and "/resource/allergen/" in str(s)}
contains = [(s, o) for s, o in explicit.subject_objects(CONTAINS)]
print(f"\nRandom-guess MRR, Exp 1 (containsAllergen, {len(allergens)} allergens): "
      f"{random_mrr(contains, len(allergens)):.3f}")
print(f"Random-guess MRR, Exp 2 (unsafeFor, 4 conditions): {random_mrr(unsafe, 4):.3f}")
