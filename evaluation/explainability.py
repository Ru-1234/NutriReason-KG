#!/usr/bin/env python3
"""Produces 3 explainability examples (question, retrieved facts/paths, answer) -> evaluation/results/explainability.md"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from retrieval.retriever import KGRetriever
from app import llm
QS = ["Is chocolate syrup ok for type 2 diabetes?",          # mostly explicit facts + rule threshold
      "Why is Chicken Satay unsafe for a nut allergy?",       # multi-hop, inferred hops
      "Which guideline supports the rule that makes Bacon Bits, Meatless unsafe for hypertension?"]
kg = KGRetriever()
out = ["# Explainability examples\n", "Tags: **explicit** = stored in the graph, **inferred** = derived by schema/rules, *generated text* = LLM output.\n"]
for i, q in enumerate(QS, 1):
    r = kg.retrieve(q)
    a = llm.answer_grounded(q, r)
    out.append(f"## Example {i}: {q}\n\n**Retrieval:** type `{r['type']}`, sufficient = {r['sufficient']}, entities = {[e['label'] for e in r['entities']]}\n\n**Retrieved facts**\n\n| id | tag | subject | predicate | object |\n|---|---|---|---|---|")
    used = [f for f in r["facts"]]
    for f in used[:25]:
        out.append(f"| {f['id']} | {f['tag']} | {f['subject']} | {f['predicate']} | {f['object']} |")
    out.append("\n**Reasoning paths**\n")
    for p in r["paths"][:6]:
        out.append(f"- `{p['text']}`")
    out.append(f"\n**Generated text (LLM answer):**\n\n> " + a.replace("\n", "\n> ") + "\n")
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "explainability.md"), "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))
