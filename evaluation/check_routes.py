#!/usr/bin/env python3
"""Routing check for the retriever (no LLM, no API key needed).

For each question it prints ONE line: id | type | sufficient | number of facts | fingerprint | entities.
The fingerprint is a short hash of every retrieved fact and path, so any change in what the retriever
returns (not only the route) changes the line.

  * CQ1..CQ14 = the 10 evaluation questions from evaluation/run_eval.py. These lines must be IDENTICAL
    before and after a retriever change (they are the regression test).
  * X1..X12   = extra questions (unseen / failure cases). These lines are allowed to change; that is the fix.

Usage (from the repo root):
  python evaluation/check_routes.py                  # print only
  python evaluation/check_routes.py --save before    # also write evaluation/results/routes_before.txt
  python evaluation/check_routes.py --save after     # write routes_after.txt and compare with routes_before.txt
  python evaluation/check_routes.py -v               # also print the reason for every question

The script always runs with PYTHONHASHSEED=0 (see below), so the output is the same on every run.
"""
import hashlib, json, os, subprocess, sys

# rdflib returns rows of queries without ORDER BY in an order that depends on Python's string-hash seed, which is
# random for every new process. Then two runs of the SAME code can pick different example rows and give different
# fingerprints. Fix the seed so "before" and "after" runs are comparable: restart this script once with seed 0.
if os.environ.get("PYTHONHASHSEED") != "0":
    sys.exit(subprocess.run([sys.executable] + sys.argv, env={**os.environ, "PYTHONHASHSEED": "0"}).returncode)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from retrieval.retriever import KGRetriever

# Same 10 questions, same wording as run_eval.py (copied, because importing run_eval would call the LLM).
CQS = [
    ("CQ1", "Which dishes contain an ingredient that can trigger a nut allergy?"),
    ("CQ2", "Which foods should a person with BOTH type 2 diabetes and hypertension avoid?"),
    ("CQ4", "Which food groups have the most foods linked to an allergy?"),
    ("CQ5", "Which food group has the highest average sodium per 100 g, and what is the value?"),
    ("CQ8", "For the dish Almond Cookies, which conditions is it unsafe for and which ingredient causes each?"),
    ("CQ9", "What are the exact sugar and sodium per 100 g of Cheddar cheese, and does it pass the diabetes and hypertension rules?"),
    ("CQ11", "Which allergens appear most often across all dishes?"),
    ("CQ12", "Which dishes contain a nut allergen although no nut word appears in the dish name?"),
    ("CQ13", "Which foods have sodium above the hypertension limit, ranked highest first, with exact values?"),
    ("CQ14", "Which guideline supports the rule that makes Bacon Bits, Meatless unsafe for hypertension?"),
]
EXTRA = [
    ("X1", "Can I eat dragon fruit curry if I have a nut allergy?"),             # Fix A: unknown dish
    ("X2", "Is dragon fruit curry safe for type 2 diabetes?"),                   # Fix A: unknown dish, safe-for wording
    ("X3", "Tell me about dragon fruit curry"),                                  # Fix A: only the group Fruit matches
    ("X4", "Is unicorn stew ok for hypertension?"),                              # Fix A: unknown dish, nothing matches
    ("X5", "Which foods have sugar above the diabetes limit?"),                  # Fix B: went to the food "Sugar"
    ("X6", "Which foods exceed the sugar limit for type 2 diabetes?"),           # Fix B: other wording
    ("X7", "Which foods are safe for lactose intolerance and also low in sugar?"),
    ("X8", "Is Chicken Satay safe for someone with a nut allergy?"),
    ("X9", "Is chedar cheese high in sodium?"),                                  # typo
    ("X10", "Is Kheer a problem for a person with lactose intolerance?"),
    ("X11", "Which dishes contain wheat gluten?"),
    ("X12", "What is the capital of France?"),                                   # off-topic -> must be insufficient
]

RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def fingerprint(r):
    blob = json.dumps({"facts": r["facts"], "paths": r["paths"]}, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(blob.encode("utf-8")).hexdigest()[:8]


def line(qid, r):
    ents = ", ".join(f"{e['label']}[{e['kind']}]" for e in r["entities"]) or "-"
    return f"{qid:<5}| {r['type']:<18}| sufficient={str(r['sufficient']):<5} | facts={len(r['facts']):>3} | {fingerprint(r)} | {ents}"


def main():
    verbose = "-v" in sys.argv
    save = sys.argv[sys.argv.index("--save") + 1] if "--save" in sys.argv else None
    kg = KGRetriever()
    out = []
    for block, qs in (("CQ", CQS), ("EXTRA", EXTRA)):
        out.append(f"# {block}")
        for qid, q in qs:
            r = kg.retrieve(q)
            out.append(line(qid, r))
            if verbose or block == "EXTRA":
                out.append(f"      Q: {q}")
                out.append(f"      reason: {r['reason']}")
    text = "\n".join(out)
    print(text)
    if not save:
        return
    os.makedirs(RES, exist_ok=True)
    path = os.path.join(RES, f"routes_{save}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"\nsaved {os.path.relpath(path)}")
    before = os.path.join(RES, "routes_before.txt")
    if save != "before" and os.path.exists(before):
        cq = lambda t: [l for l in t.splitlines() if l.startswith("CQ")]
        old, new = cq(open(before, encoding="utf-8").read()), cq(text)
        changed = [(a, b) for a, b in zip(old, new) if a != b]
        if not changed and len(old) == len(new) == len(CQS):
            print(f"OK: all {len(CQS)} CQ lines are identical to routes_before.txt")
        else:
            print(f"CHANGED: {len(changed)} CQ line(s) differ from routes_before.txt -- do not commit, check these:")
            for a, b in changed:
                print("  before:", a)
                print("  after: ", b)
            sys.exit(1)


if __name__ == "__main__":
    main()
