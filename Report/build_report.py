#!/usr/bin/env python3
"""Builds the consolidated project report PDF (Report/NutriReason_KG_Report.pdf).
All numbers/tables for Iteration 2 are read from the result files, not typed in.
Usage (repo root): python Report/build_report.py [--commit <hash>]"""
import json, os, re, subprocess, sys, glob
from PIL import Image as PILImage
from fontTools.ttLib import TTFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont as RLFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak,
                                Preformatted, KeepTogether)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
FD = "C:/Windows/Fonts/"
pdfmetrics.registerFont(RLFont("Body", FD + "arial.ttf"))
pdfmetrics.registerFont(RLFont("Body-B", FD + "arialbd.ttf"))
pdfmetrics.registerFont(RLFont("Body-I", FD + "ariali.ttf"))
pdfmetrics.registerFont(RLFont("Mono", FD + "consola.ttf"))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-B", italic="Body-I", boldItalic="Body-B")
CMAP = set(TTFont(FD + "arial.ttf").getBestCmap())
CMAP_MONO = set(TTFont(FD + "consola.ttf").getBestCmap())


def clean(s, mono=False):
    s = str(s).translate({0x202f: " ", 0xa0: " ", 0x200b: None, 0x2011: "-", 0x2010: "-", 0x3010: "[", 0x3011: "]"})
    cm_ = CMAP_MONO if mono else CMAP
    return "".join(c if (ord(c) in cm_ or c in "\n\t") else "?" for c in s)


def esc(s):
    return clean(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


S = {
    "b": ParagraphStyle("b", fontName="Body", fontSize=9.5, leading=13, spaceAfter=5),
    "s": ParagraphStyle("s", fontName="Body", fontSize=8, leading=10),
    "c": ParagraphStyle("c", fontName="Body-I", fontSize=8, leading=10, textColor=colors.HexColor("#444444"), spaceAfter=8, alignment=1),
    "h1": ParagraphStyle("h1", fontName="Body-B", fontSize=15, leading=19, spaceBefore=10, spaceAfter=6, textColor=colors.HexColor("#14365d")),
    "h2": ParagraphStyle("h2", fontName="Body-B", fontSize=11.5, leading=15, spaceBefore=8, spaceAfter=4, textColor=colors.HexColor("#1f4e79")),
    "title": ParagraphStyle("t", fontName="Body-B", fontSize=24, leading=30, alignment=1, spaceAfter=8, textColor=colors.HexColor("#14365d")),
    "sub": ParagraphStyle("sub", fontName="Body", fontSize=12, leading=16, alignment=1, spaceAfter=4),
    "mono": ParagraphStyle("m", fontName="Mono", fontSize=7.5, leading=9.5),
}
story = []
H1 = lambda t: story.append(Paragraph(esc(t), S["h1"]))
H2 = lambda t: story.append(Paragraph(esc(t), S["h2"]))
B = lambda t: story.append(Paragraph(clean(t).replace("&", "&amp;").replace("<b>", "\x01").replace("</b>", "\x02").replace("<i>", "\x03").replace("</i>", "\x04")
                                     .replace("<", "&lt;").replace(">", "&gt;").replace("\x01", "<b>").replace("\x02", "</b>").replace("\x03", "<i>").replace("\x04", "</i>"), S["b"]))
SP = lambda h=0.2: story.append(Spacer(1, h * cm))
cell = lambda t, st="s": Paragraph(esc(t), S[st])


def table(rows, widths, header=True, fs=8):
    data = [[cell(c) if not hasattr(c, "wrap") else c for c in r] for r in rows]
    t = Table(data, colWidths=[w * cm for w in widths], repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    if header:
        st.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce6f1")))
    t.setStyle(TableStyle(st))
    story.append(t)
    SP(0.3)


def code(txt, maxw=105):
    lines = []
    for l in clean(txt, mono=True).splitlines():
        while len(l) > maxw:
            lines.append(l[:maxw]); l = "    " + l[maxw:]
        lines.append(l)
    story.append(Preformatted("\n".join(lines), S["mono"], dedent=0))
    SP(0.2)


def img(path, caption, width=15.5, maxh=11):
    if not os.path.exists(path):
        print("missing image", path); return
    w, h = PILImage.open(path).size
    wd = width * cm; ht = wd * h / w
    if ht > maxh * cm:
        ht = maxh * cm; wd = ht * w / h
    story.append(KeepTogether([Image(path, width=wd, height=ht), Paragraph(esc(caption), S["c"])]))


# ----------------------------------------------------------------------------- data from the repo
def run(cmd):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).stdout.strip()


commit = run(["git", "rev-parse", "HEAD"])
if "--commit" in sys.argv:
    commit = sys.argv[sys.argv.index("--commit") + 1]
metrics = json.load(open(P("reasoning", "results", "metrics.json"), encoding="utf-8"))
ev = json.load(open(P("evaluation", "results", "eval_raw.json"), encoding="utf-8"))
rows_ev = ev["rows"]
REPO = "https://github.com/Ru-1234/NutriReason-KG"
LINES = []
for f in sorted(glob.glob(P("SPARQL_Queries", "CQ*.rq")), key=lambda x: int(re.findall(r"\d+", os.path.basename(x))[0])):
    t = open(f, encoding="utf-8").read().splitlines()
    LINES.append((os.path.basename(f)[:-3], [l for l in t if l.startswith("# CQ")][0].split(" - ", 1)[1],
                  next((l[2:] for l in t if l.startswith("# Category")), "")))

# ----------------------------------------------------------------------------- cover
story.append(Spacer(1, 3 * cm))
story.append(Paragraph("NutriReason-KG", S["title"]))
story.append(Paragraph("A Knowledge-Grounded Advisory System for Health-Constrained Dietary Planning", S["sub"]))
story.append(Paragraph("AI-3001 Knowledge Representation &amp; Reasoning - Course Project Report (Iterations 1 and 2)", S["sub"]))
SP(1)
table([["Team", "krr-08-nutrireason"], ["Instructor", "Ms. Mehreen Javaid"],
       ["Members (GitHub)", "Romaisa (Ru-1234, repository owner) | Maham Anjum (mahamanjum99) | Zamin Muhammad (zamin-muhammad)"],
       ["GitHub repository", REPO], ["Submission commit (code)", commit],
       ["Demo video (3-5 min)", "<<ADD LINK: recorded demonstration of the running app>>"],
       ["Date", "November 2026"]], [4.5, 11.5], header=False)
B("<b>Repository access:</b> the instructor has been invited as a collaborator on the repository (see the invitation sent before the deadline). "
  "The repository contains the complete source code, ontology, RDF data, SPARQL queries, reasoning outputs, retrieval code, prompts, evaluation results and original data. "
  "No API keys are committed; <i>.env.example</i> holds the sample configuration.")
story.append(PageBreak())

# ----------------------------------------------------------------------------- 1 problem
H1("1. Problem statement and domain")
B("People with food allergies or diet-related conditions (nut allergy, lactose intolerance, type 2 diabetes, hypertension) must check every food and dish against several constraints at once: allergens hidden in ingredients, nutrient limits (sugar, sodium) and the guideline behind each rule. "
  "General-purpose LLM chatbots answer such questions fluently but can invent foods, numbers and sources, which is unacceptable in a safety setting. "
  "NutriReason builds an RDF knowledge graph from four datasets (allergen groups, dish recipes, USDA nutrients, curated guideline rules), reasons over it symbolically (OWL schema constructs and SPARQL rules) and with a link-prediction model, and then uses the graph at query time to ground an LLM so that every answer is traceable to explicit or inferred facts, or declared 'insufficient evidence'.")

# ----------------------------------------------------------------------------- 2 CQ
H1("2. Competency questions and CQ-to-KG mapping (Iteration 1)")
B("Fourteen competency questions were finalised (more than 4 multi-hop, 2 inference, 2 aggregation/filtering, and several that an LLM cannot answer without this dataset). Each maps to KG elements as shown; the SPARQL files are in <i>SPARQL_Queries/</i>.")
table([["ID", "Competency question", "Category / KG path (from the query header)"]] + [[a, b, c.replace("Category: ", "")] for a, b, c in LINES], [1.2, 6.6, 8.2])

# ----------------------------------------------------------------------------- 3 ontology / KG
H1("3. Ontology and knowledge graph design")
B("<b>T-Box (Ontology/nutrireason_tbox.ttl, built in Protégé).</b> 12 core classes (Food, Dish, Ingredient, FoodGroup, FoodType, FoodClass, Allergen with Nut/TreeNut/Peanut/Dairy/Gluten subclasses, HealthCondition with FoodAllergy/FoodIntolerance/ChronicDisease, Nutrient, DietaryRule, Guideline) plus the inferred classes HighSugarFood, HighSodiumFood, LowSugarFood; "
  "10 object properties (hasIngredient, isIngredientOf, containsAllergen, belongsToGroup, partOfCategory, triggers, unsafeFor, hasRule, appliesTo, hasSource, restrictsNutrient) and 5 datatype properties (sugarPer100g, sodiumPer100g, caloriesPer100g, thresholdValue, ruleAction).")
B("<b>Reasoning-enabling constructs:</b> RC1 subclass hierarchy (PeanutAllergen is a NutAllergen); RC2 hasValue restriction (NutAllergen triggers NutAllergy); RC3 transitive property partOfCategory; RC4 inverse property hasIngredient / isIngredientOf; RC5 property chain hasIngredient o containsAllergen -> containsAllergen; RC6 SWRL rules R1-R4 (+R5), re-implemented as SPARQL INSERT rules (Ontology/rules_graphdb.ru) because GraphDB does not execute SWRL.")
B("<b>A-Box.</b> Generated by build_kg.py from D1 (food allergens: groups, types, classes), D2 (259 dishes and ingredients), D3 (USDA nutrients, 5,140 foods) and D4 (5 dietary rules). "
  "Counts verified with rdflib in this iteration: <b>42,424 explicit triples</b> (T-Box + A-Box), <b>+7,609 inferred</b> by the rules = 50,033 total, far above the 500-triple minimum. The same counts were confirmed in GraphDB 11.5.1 after the Iteration 2 reload (Figure 3).")
B("<b>URI design.</b> Vocabulary uses a hash namespace (http://example.org/nutrireason# , prefix nr:), instances a slash namespace (.../resource/&lt;kind&gt;/&lt;slug&gt;) with kinds food, dish, ingredient, group, type, class, allergen, rule. Slug = lower-case ASCII with underscores (Almond Cookies -> dish/almond_cookies). Schema and data are separated; the same label in different kinds never clashes.")
B("<b>Data cleaning (summary).</b> All CSVs read as text; whitespace and BOM removed; missing markers (None, N/A, NaN, '-') treated as null; exact duplicates and key duplicates dropped; USDA rows with missing/negative calories, sodium or sugar removed; D1 plurals folded for matching (almonds -> almond); allergens in D2 not explained by any ingredient asserted on the dish. Details: Report/DATA_PIPELINE.md.")
img(P("Visualization", "protege_class_hierarchy.png"), "Figure 1. Class hierarchy in Protégé.", 13, 8)
img(P("Visualization", "graphdb_visual_graph.png"), "Figure 2. GraphDB visual graph of part of the knowledge graph.", 14, 9)
img(P("Results", "00_import_count.png"), "Figure 3. GraphDB import: triple count after loading T-Box and A-Box.", 14, 7)

# ----------------------------------------------------------------------------- 4 SPARQL
H1("4. SPARQL queries and outputs")
B("Fourteen queries (CQ1-CQ14) plus three inference demos run in GraphDB. Coverage: basic graph patterns (CQ4, CQ5, CQ9), FILTER (CQ2, CQ6, CQ9, CQ12, CQ13), OPTIONAL (CQ9, CQ13), UNION (CQ1, CQ8), aggregation (CQ4, CQ5, CQ11), multi-hop (CQ1, CQ6, CQ8, CQ12, CQ14), property paths (CQ1, CQ7, CQ8) and inference-dependent queries (CQ1, CQ3, CQ8, CQ10, CQ12, CQ14). "
  "The same queries also run offline with <i>run_all_queries.py</i> (rdflib).")
for c, cap in [("CQ1", "Figure 4. CQ1 (multi-hop + inference): foods/dishes that can trigger a nut allergy, GraphDB output."),
               ("CQ2", "Figure 5. CQ2 (UNION of rules R2, R3): foods to avoid with type 2 diabetes and hypertension."),
               ("CQ4", "Figure 6. CQ4 (aggregation): food groups with most allergy-linked foods."),
               ("CQ5", "Figure 7. CQ5 (aggregation): average sodium per food group."),
               ("CQ8", "Figure 8. CQ8 (multi-hop): unsafe conditions of Almond Cookies and the ingredient causing each."),
               ("CQ9", "Figure 9. CQ9 (FILTER/OPTIONAL): exact sugar and sodium, rule pass/fail."),
               ("CQ12", "Figure 10. CQ12 (multi-hop): dishes with a hidden nut allergen."),
               ("CQ14", "Figure 11. CQ14 (multi-hop): Food -> unsafeFor -> Condition -> hasRule -> Rule -> hasSource -> Guideline.")]:
    img(P("Results", c + ".png"), cap, 14.5, 7.5)

H1("5. Symbolic inference examples (explicit facts -> rule/schema -> inferred fact)")
table([["#", "Explicit facts", "Rule / schema knowledge", "Inferred fact"],
       ["1", "dish:chicken_satay hasIngredient Peanut butter; Peanut butter containsAllergen alg:peanut; alg:peanut a PeanutAllergen",
        "RC1 PeanutAllergen subClassOf NutAllergen; RC2 NutAllergen triggers NutAllergy; RC5 property chain; R1 containsAllergen(f,a) and triggers(a,c) -> unsafeFor(f,c)",
        "alg:peanut triggers NutAllergy; Chicken Satay containsAllergen peanut; Chicken Satay unsafeFor NutAllergy"],
       ["2", "food:salt_table sodiumPer100g 38758.00; food:cheese_cheddar sodiumPer100g 621.00",
        "R3 sodiumPer100g(f,n) and n > 600 -> HighSodiumFood(f) and unsafeFor(f, Hypertension); 600 mg from rule node (WHO)",
        "Salt, Table is a HighSodiumFood and unsafeFor Hypertension (also Cheddar: 621 > 600)"],
       ["3", "food:broccoli_raw sugarPer100g 1.70", "R4 sugarPer100g(f,s) and s <= 5 -> LowSugarFood(f)", "Broccoli, raw is a LowSugarFood"]],
      [0.6, 5, 6, 4.4])
img(P("Results", "inference1_allergen.png"), "Figure 12. Inference 1 (allergen inheritance) after running the rules in GraphDB (0 rows before).", 13.5, 6.5)
img(P("Results", "inference2_sodium.png"), "Figure 13. Inference 2 (high-sodium rule).", 13.5, 6.5)
img(P("Results", "inference3_lowsugar.png"), "Figure 14. Inference 3 (low-sugar classification).", 13.5, 6.5)

# ----------------------------------------------------------------------------- 6 modern reasoning
H1("6. Modern KG reasoning: link prediction with knowledge-graph embeddings (Option A)")
H2("6.1 Method (in our own words)")
B("A knowledge-graph embedding model gives every entity and relation a vector and defines a score function f(h, r, t) that should be high for true triples and low for corrupted ones. "
  "<b>TransE</b> (Bordes et al., 2013) treats a relation as a translation in vector space, so a true triple should satisfy h + r = t and the score is -||h + r - t||. It is simple and fast but cannot model one-to-many relations well (many dishes share one allergen). "
  "<b>RotatE</b> (Sun et al., 2019) places entities in complex space and models a relation as an element-wise rotation, t = h o r with |r_i| = 1; this can represent symmetry, inversion and composition patterns and is trained with self-adversarial negative sampling. "
  "We train both with PyKEEN (Ali et al., 2021), which provides the models, the negative-sampling training loop and the evaluation protocol. "
  "Link prediction asks the model for the missing tail in (head, relation, ?), then ranks all entities by score.")
B("<b>Why it suits this domain.</b> The graph has regular structure (dish -> ingredient -> allergen -> condition). If a containsAllergen link is missing from the data (e.g. a recipe lacking an allergen annotation), an embedding trained on the neighbouring structure can propose it for human review, complementing the exact but incomplete symbolic rules.")
H2("6.2 Experimental setup")
B(f"<b>Data:</b> all entity-entity triples of the graph (rdf:type, subClassOf and nr: object properties; literals excluded). "
  f"<b>Experiment 1</b> uses the explicit graph (train+test) and hides 15% of the nr:containsAllergen triples. <b>Experiment 2</b> uses the explicit + rule-inferred graph and hides 15% of the nr:unsafeFor triples. "
  f"Held-out triples are chosen so every entity keeps at least one training edge. 3 random splits (seeds 0-2); {metrics['config']['epochs']} epochs, embedding dimension {metrics['config']['dim']}, Adam, 32 negatives per positive. "
  "<b>Metrics:</b> filtered tail ranking (other known true tails are removed from the candidate list): MRR and Hits@1/3/10, mean +- standard deviation over splits. "
  "<b>Baseline:</b> a popularity baseline that ranks tails by how often they were a tail of that relation in training (expected rank under random tie-breaking).")
def fm(d, k):
    return f"{d[k][0]:.3f} ± {d[k][1]:.3f}"
for key, title in [("exp1_containsAllergen_explicit", "Experiment 1: hold out 15% of nr:containsAllergen (explicit graph)"),
                   ("exp2_unsafeFor_materialised", "Experiment 2: hold out 15% of nr:unsafeFor (explicit + inferred graph)")]:
    H2("6.3 Results - " + title if key.startswith("exp1") else "Results - " + title)
    table([["Model", "MRR", "Hits@1", "Hits@3", "Hits@10", "# test links"]] +
          [[m, fm(d, "MRR"), fm(d, "Hits@1"), fm(d, "Hits@3"), fm(d, "Hits@10"), str(d["n_test"])] for m, d in metrics[key].items()],
          [4, 2.6, 2.6, 2.6, 2.6, 1.6])
B("<b>Reading the results.</b> Hits@k is the fraction of held-out links whose true tail is in the model's top k; MRR is the mean of 1/rank. "
  "<b>Experiment 1 (the meaningful test):</b> RotatE clearly beats the popularity baseline (MRR 0.612 vs 0.420; type-constrained 0.852 vs 0.420), so it learns real structure about which ingredients carry which allergen. "
  "TransE is weaker (MRR 0.315, type-constrained 0.618; Hits@1 0.059 is below the baseline), consistent with TransE's known difficulty with relations where many heads share one tail (many foods contain Dairy). "
  "<b>Type-constrained ranking.</b> The models first ranked every one of the 5,871 entities, while the baseline only ever ranks real allergens or conditions. Ranking only instances of the relation's range (45 allergens, 4 conditions) is the fair comparison; both columns are reported. "
  "<b>Experiment 2 is a negative result:</b> against all entities the baseline has the best MRR (0.731 vs RotatE 0.662), but only because of the unequal ranking above. Type-constrained, the models are near-perfect (RotatE 0.994), yet only because all 2,071 unsafeFor links are produced by our own rules and leak through HighSugarFood/HighSodiumFood type triples (76% of them stay in training); random guessing among the 4 conditions already gives MRR 0.544. So Exp 2 does not show that embeddings find new knowledge; for such deterministic links the symbolic rules are the right tool. Full analysis and Experiment 3 (allergen suggestions for 289 foods with none, top 10 checked by hand): Report/LINK_PREDICTION.md.")
H2("Sample predictions (labelled as predictions)")
import csv
for name in ["predictions_exp1_containsAllergen.csv", "predictions_exp2_unsafeFor.csv"]:
    rows = list(csv.DictReader(open(P("reasoning", "results", name), encoding="utf-8")))
    sel = [r for r in rows if r["rank"] == "1"][:8]
    table([["Status", "Head", "Relation", "Top-1 predicted tail", "Score", "Equals a hidden true link?"]] +
          [[r["status"], r["head"], r["relation"], r["predicted_tail"], r["score"], "yes" if r["recovers_held_out_link"] == "True" else "no"] for r in sel],
          [3.3, 3.6, 2.8, 3.2, 1.3, 1.8])
B("<b>Prediction vs fact.</b> Every row above is a <b>PREDICTION</b>: a ranked guess from a statistical model, not a confirmed or logically inferred fact. The 'no' rows are not necessarily wrong (the link may simply be absent from the data) and need human review. "
  "Predictions are saved only in reasoning/results/ and are never loaded into the retrieval graph, so the LLM application cannot cite them as facts. Facts remain either <i>explicit</i> (stored) or <i>inferred</i> (schema/rules).")

# ----------------------------------------------------------------------------- 7 architecture
H1("7. Knowledge-grounded LLM application")
H2("7.1 Architecture")
code("""User question
   |
   v
[1] Entity linking (retrieval/retriever.py)
    condition aliases ("diabetes" -> nr:Type2Diabetes) + token-coverage match of rdfs:label
    for foods / dishes / ingredients / allergens / groups (+ typo fallback)
   |
   v
[2] Intent routing -> SPARQL template (dish profile, food profile, condition -> unsafe list,
    safe-for, both-conditions, top nutrient, rule/guideline, group aggregates, ...)
   |   executes on rdflib graphs:  explicit = tbox + abox ,  inferred-only = inferred.ttl
   v
[3] JSON {facts[id, tag explicit|inferred], paths, type, sufficient, reason, queries}
   |   sufficient = false when no entity / no matching facts
   v
[4] LLM (Groq, openai/gpt-oss-120b, T = 0) with a grounding prompt
    "answer only from context, cite [F#], say Insufficient evidence otherwise"
   |
   v
[5] Streamlit UI: question, linked entities, paths, fact table with tags, SPARQL executed, answer""")
B("<b>Design choice.</b> We use SPARQL-template-generated context (a KG-RAG variant) rather than embedding-based retrieval, because the questions need exact numbers, thresholds and multi-hop paths, and templates make each retrieved fact auditable. The approach follows the retrieve-then-generate pattern of RAG (Lewis et al., 2020) and the surveys of graph-grounded generation (Edge et al., 2024; Peng et al., 2024), with structured graph facts instead of text chunks as context.")
B("<b>Explicit vs inferred.</b> The graph is split into two files. abox.ttl + the T-Box hold the explicit triples; inferred.ttl (made by reasoning/materialize.py, i.e. the rules script run over the explicit graph) holds <i>only</i> the derived 7,609 triples. A retrieved fact is tagged explicit if it is in the first set and inferred if it is only in the second. GraphDB gives the same split by querying with inference switched off.")
B("<b>Insufficient evidence.</b> If no graph entity or supported question pattern is recognised, or the SPARQL returns no facts, the retriever returns sufficient = false and the prompt instructs the model to reply 'Insufficient evidence in the knowledge graph'. If the model is given facts that do not contain the answer it must also decline (see the unseen-question check). "
  "In Iteration 2 two retrieval gaps were fixed (Report/RETRIEVAL.md): a question about an item that is not in the graph (e.g. 'dragon fruit curry') now returns sufficient = false with the unmatched words named, instead of a list that only matched the word 'fruit'; and 'foods with sugar above the diabetes limit' now returns the list of foods above the 22.5 g threshold read from the rule node (669 foods) instead of the profile of the ingredient Sugar. evaluation/check_routes.py confirmed that the routes and facts of the 10 evaluation questions did not change.")
H2("7.2 Prompts")
from importlib import util
spec = util.spec_from_file_location("llm", P("app", "llm.py")); llm = util.module_from_spec(spec); spec.loader.exec_module(llm)
code("SYSTEM (LLM only): " + llm.SYSTEM_LLM_ONLY + "\n\nSYSTEM (KG-grounded):\n" + llm.SYSTEM_GROUNDED + "\n\nUSER (KG-grounded): CONTEXT FROM THE KNOWLEDGE GRAPH:\\n<question type | sufficiency | facts [id] (tag) s | p | o | paths>\\n\\nQUESTION: <question>", maxw=110)
img(P("Report", "screenshots", "app_dish.png"), "Figure 15. Streamlit app: retrieved paths and facts (left), grounded answer (right, blue) and the plain-LLM answer (red) for comparison.", 14.5, 14)
img(P("Report", "screenshots", "app_insufficient.png"), "Figure 16. Question about an item that is not in the graph (dragon fruit curry): the retriever returns type unknown_item with 'Sufficient evidence: NO' and the model declines instead of inventing an answer.", 14.5, 7)

# ----------------------------------------------------------------------------- 8 evaluation
H1("8. LLM-only vs KG-grounded evaluation (10 competency questions)")
B(f"Same model ({ev['model']} on Groq) and temperature ({ev['temperature']}) in both conditions. A = LLM only; B = LLM + KG retrieval. Correctness is checked automatically against verified sets/values computed from the graph with independent SPARQL (evaluation/run_eval.py), then each answer was read by hand (evaluation/manual_review.md).")
yn = lambda x: "Yes" if x else "No"
def trim(s, n=330):
    s = s.replace("**", "")
    s = re.sub(r"\s+", " ", s)
    return s if len(s) <= n else s[:n] + " ..."
table([["CQ / question", "Expected answer", "LLM only (A)", "KG-grounded (B)", "Correct? A / B", "Evidence? A / B"]] +
      [[f"{r['cq']}: {r['question']}", r["expected"], trim(r["llm_only"]), trim(r["kg_grounded"]),
        f"{yn(r['correct_A'])} / {yn(r['correct_B'])}", f"{yn(r['evidence_A'])} / {yn(r['evidence_B'])}"] for r in rows_ev],
      [2.9, 2.8, 3.9, 3.9, 1.3, 1.3])
cA, cB = sum(r["correct_A"] for r in rows_ev), sum(r["correct_B"] for r in rows_ev)
B(f"<b>Result: correct answers A = {cA}/10, B = {cB}/10. Evidence available: A = 0/10, B = {sum(r['evidence_B'] for r in rows_ev)}/10</b> (every grounded answer cites fact ids that map to tagged graph facts).")
B("<b>Unsupported / hallucinated claims (manual review).</b> LLM only: 9 of 10 answers contain claims the graph contradicts or does not contain (e.g. Pad Thai/pesto for CQ1/CQ12, 'condiments about 6000 mg' for CQ5, AHA/DASH as the guideline for CQ14 where the KG rule is WHO). The remaining one (CQ9) is approximately right (0.5 g, 620 mg) but not exact. KG-grounded: 1 of 10 (CQ1 listed 'Peanut Butter' under dishes although it is a food node).")
B("<b>Where grounding helped:</b> dataset-specific facts (counts, exact values, hidden ingredients, which guideline the rule cites) that no model can know without the graph. <b>Where it did not:</b> LLM answers on general knowledge are often plausible in the real world but answer a different question than 'what does this graph say'; list questions are capped at 12-15 rows, so answers are partial (and say so).")
B("<b>Caveat about the score.</b> The 10 questions were also used to debug the retriever (tie-breaking in entity linking, routing of 'above the limit' questions), so B = 10/10 is a development-set result. To test generalisation we ran 8 other questions (evaluation/unseen_check.py): the dish/food/safe-for/rule/insufficient cases were answered from the graph; two questions initially failed (the low-sugar rule was missing from the context; allergens with no linked condition such as gluten had no template) and the retriever was fixed afterwards. An unknown dish ('dragon fruit curry') was at first declined only by the LLM, because the retriever flagged the context as sufficient after the word 'fruit' matched a food group; this was fixed in the retriever (Fix A, Section 7.1), and the dish is now declined at retrieval time.")

# ----------------------------------------------------------------------------- 9 explainability
H1("9. Explainability and provenance")
B("For each answer the system exposes the question, retrieved facts and paths, the final answer and supporting evidence. Labels: <b>explicit</b> = stored in the graph; <b>inferred</b> = derived by schema/rules; <b>generated text</b> = the LLM's wording. No predicted link is used in any answer.")
exp_md = open(P("evaluation", "results", "explainability.md"), encoding="utf-8").read()
for blk in exp_md.split("## Example ")[1:]:
    title, rest = blk.split("\n", 1)
    H2("Example " + title)
    facts = re.findall(r"^\| (F\d+) \| (explicit|inferred) \| (.*?) \| (.*?) \| (.*?) \|$", rest, re.M)
    table([["id", "tag", "subject", "predicate", "object"]] + [list(f) for f in facts[:16]], [1.1, 1.8, 5.2, 4.2, 3.7])
    paths = re.findall(r"^- `(.*)`$", rest, re.M)
    for p in paths[:4]:
        code("path: " + p)
    gen = rest.split("**Generated text (LLM answer):**", 1)[1].strip().lstrip("> ").replace("\n> ", "\n")
    B("<b>Generated text:</b> " + esc(gen.strip()).replace("\n", "<br/>"))
B("<b>Reading example 2.</b> hasIngredient and containsAllergen hops are explicit; 'triggers' and the final 'unsafeFor' are inferred by RC2/R1. Note a data-quality finding: D1 links Peanut butter to Dairy, which makes Chicken Satay unsafe for lactose intolerance too. The system faithfully reports what the graph says; the error is in the source data, not generated by the LLM.")

# ----------------------------------------------------------------------------- 10 limitations
H1("10. Limitations")
for t in ["Retriever coverage: about a dozen question templates; questions outside them return 'insufficient' even when the graph could answer with a new template. Entity linking is lexical (labels and a small alias list). Unknown items are detected from unmatched words, but if one word of an unknown dish is itself a food (e.g. 'mango lassi' -> Mango), that food's profile is still returned and only the LLM prompt makes it decline.",
          "Open-world caveat: 'safe' means no unsafeFor fact exists. Foods without D1 allergen data are not reported as safe (the safe-for template requires a food group), but allergen annotations in D1/D2 are incomplete and sometimes wrong (e.g. Peanut butter -> Dairy). Non-allergen D1 labels such as 'Sugar' and 'Insulin' were removed in Iteration 2 (Section 3).",
          "USDA labels are abbreviated and noisy (e.g. 'Puddings, Cocnt Crm, Dry Mix'); thresholds (22.5 g sugar, 600 mg sodium per 100 g) are simplifications of the cited guidelines, applied per 100 g rather than per serving.",
          "R5 makes every dish containing table salt unsafe for hypertension, which over-flags. Nutrient values for dishes are not modelled (only ingredients).",
          "Link prediction: small graph, embedding dimension and epochs not tuned extensively; Experiment 2 has leakage by construction (see 6.3); predictions are not clinically validated.",
          "Evaluation: 10 questions, one run at T = 0, keyword-based checkers plus manual review by the team; the retriever was tuned on the same questions; a single LLM was used. This is not a statistical claim about general performance.",
          "The system is a course prototype and not medical advice."]:
    B("- " + t)

# ----------------------------------------------------------------------------- 11 contributions
H1("11. Team contributions")
log = run(["git", "log", "--format=%h|%an|%s"]).splitlines()
def commits_of(author):
    return [l for l in log if author.lower() in l.split("|")[1].lower()]
table([["Member", "GitHub", "Tasks", "Representative commits"],
       ["Romaisa", "Ru-1234", "Ontology (T-Box), build_kg.py, data cleaning, A-Box, Iteration 1 fixes (plural bug, allergen keywords, rule order), README/DATA_PIPELINE",
        "; ".join(l.split("|")[0] for l in commits_of("Romaisa")[:3]) or "-"],
       ["Maham Anjum", "mahamanjum99", "GraphDB loading, SPARQL queries CQ1-CQ14 and inference demos, GraphDB result screenshots, visual graph",
        "; ".join(l.split("|")[0] for l in commits_of("Maham")[:3]) or "-"],
       ["Zamin Muhammad", "zamin-muhammad", "Iteration 2: link prediction (reasoning/), KG retrieval layer (retrieval/), prompts + Streamlit app (app/), evaluation and explainability (evaluation/), report. Written with AI assistance (Claude Code) which was reviewed and is explained by the member.",
        "; ".join(l.split("|")[0] for l in commits_of("Zamin")[:4]) or "see git log"]],
      [2.4, 2.6, 7.5, 3.5])
B("Commit counts do not determine marks; see the repository history for the full record. <<EDIT BEFORE SUBMISSION if the division of work differs from the above.>>")

# ----------------------------------------------------------------------------- 12 refs
H1("12. References and how they informed the work")
refs = [
 ("Bordes, A., Usunier, N., Garcia-Duran, A., Weston, J., Yakhnenko, O. (2013). Translating Embeddings for Modeling Multi-relational Data. NeurIPS 26. https://papers.nips.cc/paper/2013/hash/1cecc7a77928ca8133fa24680a88d2f9-Abstract.html", "TransE score function and margin-based training; used as model 1."),
 ("Sun, Z., Deng, Z.-H., Nie, J.-Y., Tang, J. (2019). RotatE: Knowledge Graph Embedding by Relational Rotation in Complex Space. ICLR. arXiv:1902.10197", "RotatE rotation model and self-adversarial negative sampling loss; used as model 2."),
 ("Ali, M. et al. (2021). PyKEEN 1.0: A Python Library for Training and Evaluating Knowledge Graph Embeddings. JMLR 22(82). arXiv:2007.14175; documentation https://pykeen.readthedocs.io", "Training pipeline, models, negative sampling; our filtered evaluation follows its rank-based protocol."),
 ("Rossi, A., Barbosa, D., Firmani, D., Matinata, A., Merialdo, P. (2021). Knowledge Graph Embedding for Link Prediction: A Comparative Analysis. ACM TKDD 15(2). doi:10.1145/3424672", "Filtered ranking, MRR/Hits@k, importance of baselines."),
 ("Hogan, A. et al. (2021). Knowledge Graphs. ACM Computing Surveys 54(4). doi:10.1145/3447772", "Background on KG reasoning, rules and embeddings."),
 ("Lewis, P. et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS 33. arXiv:2005.11401", "Retrieve-then-generate architecture of the application."),
 ("Edge, D. et al. (2024). From Local to Global: A Graph RAG Approach to Query-Focused Summarization. arXiv:2404.16130", "Using graph structure as retrieval context."),
 ("Peng, B. et al. (2024). Graph Retrieval-Augmented Generation: A Survey. arXiv:2408.08921", "Design space of graph-grounded generation; motivated SPARQL-template retrieval."),
 ("W3C (2013). SPARQL 1.1 Query Language and SPARQL 1.1 Update. https://www.w3.org/TR/sparql11-query/", "Queries, property paths, aggregation, INSERT rules."),
 ("W3C (2012). OWL 2 Web Ontology Language Primer. https://www.w3.org/TR/owl2-primer/ ; Protégé https://protege.stanford.edu ; GraphDB documentation https://graphdb.ontotext.com", "Ontology constructs RC1-RC5, tooling."),
 ("rdflib documentation https://rdflib.readthedocs.io ; Streamlit https://docs.streamlit.io ; Groq API https://console.groq.com/docs ; OpenAI (2025) gpt-oss-120b model card, arXiv:2508.10925", "Implementation libraries and the LLM used in both evaluation conditions."),
 ("Datasets: Kaggle 'Food: Allergens and Allergies' (D1); Kaggle 'Food Ingredients and Allergens' (D2); USDA National Nutrient Database (D3); guideline sources WHO, ADA, NIH (D4).", "Source data of the knowledge graph.")]
for i, (r, use) in enumerate(refs, 1):
    B(f"[{i}] {r}<br/><i>Used for:</i> {use}")

out = P("Report", "NutriReason_KG_Report.pdf")
SimpleDocTemplate(out, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                  title="NutriReason-KG Project Report", author="Team krr-08-nutrireason").build(
    story, onFirstPage=lambda c, d: None,
    onLaterPages=lambda c, d: (c.setFont("Body", 8), c.drawRightString(A4[0] - 2 * cm, 1 * cm, f"NutriReason-KG report - page {d.page}")))
print("wrote", out)
