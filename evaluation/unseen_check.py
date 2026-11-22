#!/usr/bin/env python3
"""Generalisation check on questions that were NOT used while developing the retriever
(the 10 evaluation CQs were used for debugging, so they are a development set). Output is judged by hand
and recorded in evaluation/results/unseen_questions.md. Usage: python evaluation/unseen_check.py"""
import os, sys
# rdflib returns rows of SPARQL queries without ORDER BY in an order that depends on Python's string-hash seed,
# which is random for every new process, so two runs could send different example facts to the LLM. Fix the seed
# (same as evaluation/check_routes.py) so the retrieval context is reproducible: restart once with seed 0.
import subprocess
if os.environ.get("PYTHONHASHSEED") != "0":
    sys.exit(subprocess.run([sys.executable] + sys.argv, env={**os.environ, "PYTHONHASHSEED": "0"}).returncode)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from retrieval.retriever import KGRetriever
from app import llm
QS = ["Is Chicken Satay safe for someone with a nut allergy?",
      "Which foods are safe for lactose intolerance and also low in sugar?",
      "Is Kheer a problem for a person with lactose intolerance?",
      "Which foods have sugar above the diabetes limit?",
      "Is Salt, Table high in sodium?",
      "What is the capital of France?",
      "Can I eat dragon fruit curry if I have a nut allergy?",
      "Which dishes contain wheat gluten?",
      "Is unicorn stew ok for hypertension?"]
kg = KGRetriever()
out = ["# Unseen-question check (model %s)\n" % llm.MODEL]
for q in QS:
    r = kg.retrieve(q)
    a = llm.answer_grounded(q, r)
    out.append(f"## {q}\n- type: `{r['type']}`, sufficient: **{r['sufficient']}**, entities: {[e['label'] for e in r['entities']]}, facts: {len(r['facts'])}\n- reason: {r['reason']}\n\n**Grounded answer:** {a}\n")
    print(q, "->", r["type"], r["sufficient"], flush=True)
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "unseen_questions.md"), "w", encoding="utf-8").write("\n".join(out))
