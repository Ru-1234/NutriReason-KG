#!/usr/bin/env python3
"""
Offline test runner (no GraphDB needed). Loads T-Box + A-Box, optionally runs the rules script,
executes every SPARQL_Queries/*.rq file and writes one CSV per query into Results/.

Usage (from the repo root):
    pip install rdflib
    python run_all_queries.py --tbox Ontology/nutrireason_tbox.ttl --abox RDF_Knowledge_Graph/abox.ttl \
                              --rules Ontology/rules_graphdb.ru
Add --no-rules to see the "before inference" state (inference-dependent queries return 0 rows).
"""
import argparse, csv, glob, os
from rdflib import Graph

ap = argparse.ArgumentParser()
ap.add_argument("--tbox", default="Ontology/nutrireason_tbox.ttl")
ap.add_argument("--abox", default="RDF_Knowledge_Graph/abox.ttl")
ap.add_argument("--rules", default="Ontology/rules_graphdb.ru")
ap.add_argument("--queries", default="SPARQL_Queries")
ap.add_argument("--out", default="Results")
ap.add_argument("--no-rules", action="store_true")
a = ap.parse_args()

g = Graph()
g.parse(a.tbox, format="turtle"); g.parse(a.abox, format="turtle")
print(f"Loaded T-Box + A-Box: {len(g)} triples")
if not a.no_rules:
    n0 = len(g)
    g.update(open(a.rules, encoding="utf-8").read())
    print(f"Rules executed: +{len(g) - n0} inferred triples -> {len(g)} total")
os.makedirs(a.out, exist_ok=True)

for path in sorted(glob.glob(os.path.join(a.queries, "*.rq"))):
    name = os.path.splitext(os.path.basename(path))[0]
    res = g.query(open(path, encoding="utf-8").read())
    cols = [str(v) for v in res.vars]
    rows = [[("" if v is None else str(v).replace("http://example.org/nutrireason#", "nr:")) for v in r] for r in res]
    suffix = "_before_rules" if a.no_rules else ""
    with open(os.path.join(a.out, f"{name}{suffix}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(cols); w.writerows(rows)
    print(f"{name:32s} {len(rows):5d} rows")
