#!/usr/bin/env python3
"""Run the symbolic rules (Ontology/rules_graphdb.ru) over T-Box + A-Box with rdflib and save
ONLY the newly inferred triples to RDF_Knowledge_Graph/inferred.ttl.

Keeping explicit and inferred triples in separate files lets the retrieval layer tag every fact
as explicit or inferred without needing GraphDB. (In GraphDB the same split is possible by
querying with the 'includeInferred' switch off.)

Usage (repo root):  python reasoning/materialize.py
"""
import os
from rdflib import Graph

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

explicit = Graph()
explicit.parse(P("Ontology", "nutrireason_tbox.ttl"))
explicit.parse(P("RDF_Knowledge_Graph", "abox.ttl"))
full = Graph()
for t in explicit:
    full.add(t)
full.update(open(P("Ontology", "rules_graphdb.ru"), encoding="utf-8").read())
inferred = Graph()
for t in full:
    if t not in explicit:
        inferred.add(t)
for pfx, ns in explicit.namespaces():
    inferred.bind(pfx, ns)
out = P("RDF_Knowledge_Graph", "inferred.ttl")
inferred.serialize(out, format="turtle")
print(f"explicit={len(explicit)}  inferred={len(inferred)}  total={len(full)}  -> {out}")
