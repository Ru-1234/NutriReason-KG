#!/usr/bin/env python3
"""LLM-only vs KG-grounded evaluation on 10 competency questions (same model, same temperature).

Usage (repo root):  python evaluation/run_eval.py
Outputs: evaluation/results/eval_raw.json (full answers + retrieval), evaluation/results/results_table.md

Correctness is decided by an automatic checker against verified sets that are computed from the
graph with INDEPENDENT SPARQL (not through the retriever templates); hallucinations are then
counted by hand in evaluation/manual_review.md (see that file).
"""
import json, os, re, sys
# rdflib returns rows of SPARQL queries without ORDER BY in an order that depends on Python's string-hash seed,
# which is random for every new process, so two runs could send different example facts to the LLM. Fix the seed
# (same as evaluation/check_routes.py) so the retrieval context is reproducible: restart once with seed 0.
import subprocess
if os.environ.get("PYTHONHASHSEED") != "0":
    sys.exit(subprocess.run([sys.executable] + sys.argv, env={**os.environ, "PYTHONHASHSEED": "0"}).returncode)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from retrieval.retriever import KGRetriever
from app import llm

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(OUT, exist_ok=True)
kg = KGRetriever()
P = "PREFIX nr: <http://example.org/nutrireason#> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "


def names(sparql):
    return {str(r[0]).lower() for r in kg.G.query(P + sparql)}


NUT = names("SELECT ?l WHERE { ?d a nr:Dish ; nr:hasIngredient ?i ; rdfs:label ?l . ?i nr:containsAllergen ?a . ?a nr:triggers nr:NutAllergy }")
BOTH = names("SELECT ?l WHERE { ?f nr:unsafeFor nr:Type2Diabetes , nr:Hypertension ; rdfs:label ?l }")
HIDDEN = {"baked brie", "chicken satay", "green smoothie", "kheer", "rabri", "rasmalai"}


def has(t, *ws):
    t = re.sub(r"(?<=\d)[ ,](?=\d{3})", "", t.lower())
    return all(w.lower() in t for w in ws)


def n_from(t, S):
    t = t.lower()
    return sum(1 for s in S if re.search(r"\b" + re.escape(s) + r"\b", t))


CQS = [
    ("CQ1", "Which dishes contain an ingredient that can trigger a nut allergy?",
     f"Dishes incl. Almond Cookies, Chicken Satay, Pecan Pie, Baked Brie, Kheer, Rasmalai, Rabri, Green Smoothie ({len(NUT)} in KG)",
     lambda a: n_from(a, NUT) >= 4),
    ("CQ2", "Which foods should a person with BOTH type 2 diabetes and hypertension avoid?",
     f"{len(BOTH)} foods unsafe for both, e.g. Gravy Pork Dry, Hoisin sauce, Puddings Vanilla Dry Mix",
     lambda a: n_from(a, BOTH) >= 2),
    ("CQ4", "Which food groups have the most foods linked to an allergy?",
     "Dairy (181), Offal (155), Pulse (83), Cereal grain (66), Potato (57)",
     lambda a: has(a, "dairy", "181")),
    ("CQ5", "Which food group has the highest average sodium per 100 g, and what is the value?",
     "Egg, 523 mg (then Dairy 370, Fish 304)",
     lambda a: has(a, "egg") and ("523" in a or "522.8" in a)),
    ("CQ8", "For the dish Almond Cookies, which conditions is it unsafe for and which ingredient causes each?",
     "Nut allergy <- Almonds; Lactose intolerance <- Butter; Type 2 diabetes <- Sugar",
     lambda a: has(a, "almond", "butter", "sugar", "nut", "lactose", "diabetes")),
    ("CQ9", "What are the exact sugar and sodium per 100 g of Cheddar cheese, and does it pass the diabetes and hypertension rules?",
     "Sugar 0.52 g (passes), sodium 621 mg > 600 (fails hypertension)",
     lambda a: has(a, "0.52", "621")),
    ("CQ11", "Which allergens appear most often across all dishes?",
     "Dairy 137 dishes, Wheat/Gluten 59, Chicken 44, Allium 24, Soy/Legume 24",
     lambda a: has(a, "dairy", "137")),
    ("CQ12", "Which dishes contain a nut allergen although no nut word appears in the dish name?",
     "Baked Brie, Chicken Satay, Green Smoothie, Kheer, Rabri, Rasmalai",
     lambda a: n_from(a, HIDDEN) >= 4),
    ("CQ13", "Which foods have sodium above the hypertension limit, ranked highest first, with exact values?",
     "Salt, Table 38,758 mg; Baking soda 27,360; Beef broth powder 26,000 (902 foods > 600 mg)",
     lambda a: has(a, "salt") and "38758" in re.sub(r"(?<=\d)[ ,](?=\d{3})", "", a)),
    ("CQ14", "Which guideline supports the rule that makes Bacon Bits, Meatless unsafe for hypertension?",
     "Bacon bits -> Hypertension -> sodium rule -> WHO",
     lambda a: ("world health organization" in a.lower() or re.search(r"\bwho\b", a, re.I) is not None)),
]

rows = []
RESCORE = "--rescore" in sys.argv   # re-apply the checkers to the saved answers without calling the LLM again
saved = {x["cq"]: x for x in json.load(open(os.path.join(OUT, "eval_raw.json"), encoding="utf-8"))["rows"]} if RESCORE else {}
for cid, q, exp, chk in CQS:
    print(cid, flush=True)
    if RESCORE:
        a, b = saved[cid]["llm_only"], saved[cid]["kg_grounded"]
        r = kg.retrieve(q)
    else:
        a = llm.answer_llm_only(q)
        r = kg.retrieve(q)
        b = llm.answer_grounded(q, r)
    ev_b = bool(r["sufficient"] and re.search(r"[\[【［(]\s*F\s*\d+", b))   # [F3], [ F3 ], 【F3】, ［F3］, (F3)
    rows.append({"cq": cid, "question": q, "expected": exp, "llm_only": a, "kg_grounded": b,
                 "correct_A": bool(chk(a)), "correct_B": bool(chk(b)), "evidence_A": False, "evidence_B": ev_b,
                 "retrieval": {k: r[k] for k in ("type", "sufficient", "reason", "entities")}, "n_facts": len(r["facts"])})
json.dump({"model": llm.MODEL, "temperature": llm.TEMPERATURE, "rows": rows}, open(os.path.join(OUT, "eval_raw.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
yn = lambda x: "Yes" if x else "No"
with open(os.path.join(OUT, "results_table.md"), "w", encoding="utf-8") as f:
    f.write(f"Model: {llm.MODEL}, temperature {llm.TEMPERATURE}\n\n| CQ | Question | Expected | LLM only | KG-grounded | Correct? A / B | Evidence? A / B |\n|---|---|---|---|---|---|---|\n")
    sh = lambda s: s.replace("\n", " ").replace("|", "/")[:260]
    for x in rows:
        f.write(f"| {x['cq']} | {x['question']} | {x['expected']} | {sh(x['llm_only'])} | {sh(x['kg_grounded'])} | {yn(x['correct_A'])} / {yn(x['correct_B'])} | {yn(x['evidence_A'])} / {yn(x['evidence_B'])} |\n")
    f.write(f"\nCorrect: A = {sum(x['correct_A'] for x in rows)}/10, B = {sum(x['correct_B'] for x in rows)}/10\n")
print(open(os.path.join(OUT, "results_table.md"), encoding="utf-8").read()[-300:])
