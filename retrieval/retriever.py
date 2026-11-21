#!/usr/bin/env python3
"""KG retrieval layer for NutriReason (the "KG retrieval / reasoning" box of the architecture).

    question --> entity linking --> intent detection --> SPARQL template(s) --> JSON

Return value of ``KGRetriever.retrieve(question)``::

    {"question": str,
     "type": "dish_profile" | "food_profile" | "condition_unsafe" | "safe_for" | "rule_info" | ... | "none",
     "entities": [{"label", "uri", "kind", "matched_text"}],
     "facts":  [{"id": "F1", "subject", "predicate", "object", "tag": "explicit" | "inferred"}],
     "paths":  [{"text": "Dish -[hasIngredient]-> ... ", "fact_ids": ["F1", ...], "tags": [...]}],
     "queries": [SPARQL strings that were executed],
     "sufficient": bool, "reason": str}

Explicit vs inferred: the graph is kept as two rdflib graphs. ``RDF_Knowledge_Graph/abox.ttl`` +
``Ontology/nutrireason_tbox.ttl`` hold the explicit triples; ``RDF_Knowledge_Graph/inferred.ttl``
(made by ``reasoning/materialize.py`` = the rules script run over the explicit graph) holds ONLY
the derived triples. A fact is tagged "explicit" if it is in the first graph, "inferred" if only in
the second. (In GraphDB the same split = query with "include inferred" switched off.)
Link-prediction output is never loaded here, so predictions can never appear as facts.
"""
import os, re, difflib
from rdflib import Graph, URIRef, Literal, RDF, RDFS, Namespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NR = Namespace("http://example.org/nutrireason#")
PREFIXES = """PREFIX nr: <http://example.org/nutrireason#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""
STOP = set("""a an the is are was were be been of for to in on at by with and or not no do does did can could should
would i me my we you it its this that these those what which who whom how why when where there any all both
from as about than then so if into out up down over under more most much many some such only also have has had
eat eating food foods dish dishes safe unsafe person people someone anyone""".split())
# words that must not be matched as entity names on their own
GENERIC = {"food", "dish", "foods", "dishes", "type", "group", "class", "rule", "allergen", "allergy", "allergies",
           "nutrient", "oil", "raw"}

CONDITION_ALIASES = {
    "nut allergy": "NutAllergy", "nut allergies": "NutAllergy", "nut allergic": "NutAllergy", "nuts": "NutAllergy",
    "peanut allergy": "NutAllergy", "tree nut allergy": "NutAllergy", "nut allergen": "NutAllergy",
    "lactose intolerance": "LactoseIntolerance", "lactose intolerant": "LactoseIntolerance", "lactose": "LactoseIntolerance",
    "dairy allergy": "LactoseIntolerance", "type 2 diabetes": "Type2Diabetes", "type2 diabetes": "Type2Diabetes",
    "type ii diabetes": "Type2Diabetes", "diabetes": "Type2Diabetes", "diabetic": "Type2Diabetes", "t2d": "Type2Diabetes",
    "hypertension": "Hypertension", "high blood pressure": "Hypertension", "blood pressure": "Hypertension",
    "hypertensive": "Hypertension",
}
NUTRIENT_PROPS = {"sugar": "sugarPer100g", "sodium": "sodiumPer100g", "salt": "sodiumPer100g", "calories": "caloriesPer100g",
                  "calorie": "caloriesPer100g", "energy": "caloriesPer100g"}
# Fix A: question words that describe the request, not an item. Any other content word that no linked
# entity explains is treated as part of an item name the graph does not know (e.g. "dragon", "curry").
INTENT_WORDS = set("""eat ate drink consume have having suffer suffering get take tell give show list explain
ok okay fine good bad healthy unhealthy harmful dangerous risky risk problem problems issue issues allowed
allergy allergies allergic intolerance intolerant condition conditions diabetes diabetic diabetics hypertension
hypertensive lactose nut nuts peanut sugar sodium salt calorie calories energy
contain contains ingredient ingredients avoid limit limits high low value values exact per g mg gram grams
above below over under rule rules guideline guidelines amount level levels much many lot lots
please kindly okay yes""".split())
YESNO_STARTS = ("is ", "are ", "can ", "could ", "should ", "may ", "am ", "do ", "does ", "will ", "would ")


def norm(s):
    s = re.sub(r"[^a-z0-9 ]+", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def toks(s):
    return [stem(w) for w in norm(s).split() if w not in STOP]


class KGRetriever:
    def __init__(self, tbox=None, abox=None, inferred=None, max_facts=40):
        self.E = Graph()
        self.E.parse(tbox or os.path.join(ROOT, "Ontology", "nutrireason_tbox.ttl"))
        self.E.parse(abox or os.path.join(ROOT, "RDF_Knowledge_Graph", "abox.ttl"))
        self.I = Graph()
        inf = inferred or os.path.join(ROOT, "RDF_Knowledge_Graph", "inferred.ttl")
        if os.path.exists(inf):
            self.I.parse(inf)
        self.G = Graph()
        for t in self.E:
            self.G.add(t)
        for t in self.I:
            self.G.add(t)
        self.max_facts = max_facts
        self._build_index()

    # ------------------------------------------------------------------ index / entity linking
    def label(self, node):
        if isinstance(node, Literal):
            v = node.toPython()
            return str(v)
        l = self.G.value(node, RDFS.label)
        return str(l) if l else str(node).rsplit("/", 1)[-1].rsplit("#", 1)[-1]

    def kind_of(self, uri):
        types = set(self.G.objects(uri, RDF.type))
        if NR.Dish in types:
            return "Dish"
        if types & {NR.FoodGroup}:
            return "FoodGroup"
        if types & {NR.FoodType}:
            return "FoodType"
        if types & {NR.FoodClass}:
            return "FoodClass"
        if any((t, RDFS.subClassOf, NR.Allergen) in self.G or t == NR.Allergen for t in types):
            return "Allergen"
        if types & {NR.FoodAllergy, NR.FoodIntolerance, NR.ChronicDisease}:
            return "Condition"
        if NR.Ingredient in types and NR.Food in types:
            return "Food"
        if NR.Ingredient in types:
            return "Ingredient"
        if NR.Food in types or any((t, RDFS.subClassOf, NR.Food) in self.G for t in types):
            return "Food"
        if NR.Nutrient in types:
            return "Nutrient"
        if NR.Guideline in types:
            return "Guideline"
        return None

    def _build_index(self):
        self.entities = []  # (uri, label, kind, tokens)
        for s in set(self.G.subjects(RDFS.label, None)):
            if not isinstance(s, URIRef) or not str(s).startswith("http://example.org/nutrireason"):
                continue
            k = self.kind_of(s)
            if k in (None, "Nutrient", "Guideline") and k is None:
                continue
            if k is None:
                continue
            lab = str(self.G.value(s, RDFS.label))
            t = toks(lab)
            if t:
                self.entities.append((s, lab, k, t, set(t)))
        self.cond_uri = {k: NR[v] for k, v in CONDITION_ALIASES.items()}
        self.cond_label = {u: self.label(u) for u in set(self.cond_uri.values())}
        self.rule_thr = {}
        for r in self.G.subjects(RDF.type, NR.DietaryRule):
            self.rule_thr[r] = (self.G.value(r, NR.thresholdValue), self.G.value(r, NR.ruleAction))
        self.sugar_limit = float(self.G.value(URIRef("http://example.org/nutrireason/resource/rule/type2diabetes_sugar_avoid"), NR.thresholdValue))
        self.sodium_limit = float(self.G.value(URIRef("http://example.org/nutrireason/resource/rule/hypertension_sodium_avoid"), NR.thresholdValue))

    def link(self, question):
        qn = norm(question)
        qt_list = toks(question)
        qt = set(qt_list)
        found = []
        # 1. health conditions via alias phrases (longest alias first)
        used = set()
        for alias in sorted(CONDITION_ALIASES, key=len, reverse=True):
            if re.search(r"\b" + re.escape(alias) + r"\b", qn) and CONDITION_ALIASES[alias] not in used:
                u = NR[CONDITION_ALIASES[alias]]
                used.add(CONDITION_ALIASES[alias])
                found.append({"label": self.label(u), "uri": str(u), "kind": "Condition", "matched_text": alias, "score": 10})
                qt -= set(toks(alias))  # words explained by a condition must not also match foods ("nut", "sugar"...)
        # 2. labels of foods / dishes / ingredients / allergens / groups by token coverage
        cands = []
        for uri, lab, kind, t, tset in self.entities:
            if kind == "Condition":
                continue
            if len(tset) == 1 and next(iter(tset)) in GENERIC:
                continue
            m = tset & qt
            if not m:
                continue
            cov = len(m) / len(tset)
            if cov == 1 or (len(m) >= 2 and cov >= 0.6):
                prio = {"Dish": 5, "Food": 4, "Ingredient": 3, "Allergen": 3, "FoodGroup": 2, "FoodType": 2, "FoodClass": 2}.get(kind, 1)
                cands.append((cov == 1, len(m), cov, prio, -len(tset), uri, lab, kind, m))
        cands.sort(key=lambda c: (c[0], c[2], c[1], c[3], c[4]), reverse=True)  # full coverage first, then partial
        covered = set()
        for full, n, cov, prio, nl, uri, lab, kind, m in cands:
            if m <= covered and covered:
                continue
            # a single weak (partial) token match is not enough
            found.append({"label": lab, "uri": str(uri), "kind": kind, "matched_text": " ".join(sorted(m)), "score": n + cov})
            covered |= m
            if len(found) >= 6:
                break
        # 3. fuzzy single-word fallback for typos (only if nothing matched yet)
        if not any(f["kind"] != "Condition" for f in found):
            words = [w for w in norm(question).split() if w not in STOP and len(w) > 4]
            best = None
            for w in words:
                for uri, lab, kind, t, tset in self.entities:
                    if kind == "Condition" or len(tset) > 2:
                        continue
                    for lt in t:
                        r = difflib.SequenceMatcher(None, w, lt).ratio()
                        if r >= 0.86 and (best is None or r > best[0]):
                            best = (r, uri, lab, kind, w)
            if best:
                found.append({"label": best[2], "uri": str(best[1]), "kind": best[3], "matched_text": best[4], "score": best[0]})
        return found

    def unexplained(self, question, ents):
        """Fix A. Content words of the question that no linked entity explains and that are not request words.
        Example: "Can I eat dragon fruit curry if I have a nut allergy?" links only Fruit (food group) and
        Nut allergy, so "dragon" and "curry" are left over -> the dish named in the question is not in the graph."""
        covered = set()
        for e in ents:
            covered |= set(toks(e["matched_text"]))
        intent = {stem(w) for w in INTENT_WORDS}
        out = []
        for w in toks(question):
            if w in covered or w in intent or w.isdigit() or len(w) < 3 or w in out:
                continue
            out.append(w)
        return out

    # ------------------------------------------------------------------ helpers
    def tag(self, s, p, o):
        if (s, p, o) in self.E:
            return "explicit"
        if (s, p, o) in self.I:
            return "inferred"
        return None

    def q(self, ctx, sparql):
        ctx["queries"].append(sparql.strip())
        return list(self.G.query(PREFIXES + sparql))

    def add_fact(self, ctx, s, p, o, tag=None):
        tg = tag or self.tag(s, p, o)
        if tg is None:
            return None
        key = (s, p, o)
        if key in ctx["_fid"]:
            return ctx["_fid"][key]
        fid = f"F{len(ctx['facts']) + 1}"
        pname = str(p).replace(str(NR), "nr:").replace(str(RDF), "rdf:").replace(str(RDFS), "rdfs:")
        ctx["facts"].append({"id": fid, "subject": self.label(s), "predicate": pname, "object": self.label(o), "tag": tg})
        ctx["_fid"][key] = fid
        return fid

    def add_path(self, ctx, steps):
        """steps = [(s, p, o), ...] chained triples; text shows the chain with an explicit/inferred tag per hop."""
        ids, tags, parts = [], [], []
        for i, (s, p, o) in enumerate(steps):
            fid = self.add_fact(ctx, s, p, o)
            if fid is None:
                return
            ids.append(fid)
            tg = ctx["facts"][int(fid[1:]) - 1]["tag"]
            tags.append(tg)
            pn = str(p).replace(str(NR), "")
            if i == 0:
                parts.append(self.label(s))
            parts.append(f"-[{pn} ({tg[:3]})]->")
            parts.append(self.label(o))
        ctx["paths"].append({"text": " ".join(parts), "fact_ids": ids, "tags": tags})

    def add_nutrient(self, ctx, node, prop):
        v = self.G.value(node, NR[prop])
        if v is not None:
            self.add_fact(ctx, node, NR[prop], v, "explicit")
        return v

    # ------------------------------------------------------------------ main entry point
    def retrieve(self, question):
        ctx = {"question": question, "type": "none", "entities": [], "facts": [], "paths": [], "queries": [],
               "sufficient": False, "reason": "", "_fid": {}}
        ents = self.link(question)
        ctx["entities"] = [{k: v for k, v in e.items() if k != "score"} for e in ents]
        qn = norm(question)
        words = set(qn.split())
        conds = [URIRef(e["uri"]) for e in ents if e["kind"] == "Condition"]
        others = [e for e in ents if e["kind"] != "Condition"]
        dish = next((URIRef(e["uri"]) for e in others if e["kind"] == "Dish"), None)
        food = next((URIRef(e["uri"]) for e in others if e["kind"] in ("Food", "Ingredient")), None)
        alg = next((URIRef(e["uri"]) for e in others if e["kind"] == "Allergen"), None)
        grp = next((URIRef(e["uri"]) for e in others if e["kind"] in ("FoodGroup", "FoodType", "FoodClass")), None)
        nutrient = next((NUTRIENT_PROPS[w] for w in qn.split() if w in NUTRIENT_PROPS), None)
        has = lambda *ks: any(re.search(r"\b" + k + r"\b", qn) for k in ks)
        if dish and (nutrient or has("per 100 g", "per 100g", "exact", "pass", "passes")):
            # a Dish node carries no nutrient values: if a USDA Food with the same name exists, use it
            dt = set(toks(self.label(dish)))
            alt = [u for u, lab, k, t, ts in self.entities if k == "Food" and ts and ts <= dt
                   and self.G.value(u, NR.sugarPer100g) is not None]
            if alt:
                food, dish = sorted(alt, key=lambda u: len(str(u)))[0], None

        # Fix A: the question names an item (dish/food) that the graph does not know. Only a food group, type
        # or class (or nothing) was linked, and some content words stay unexplained.
        unknown = self.unexplained(question, ents)
        unknown_item = bool(unknown) and not (dish or food or alg)
        yes_no = qn.startswith(YESNO_STARTS)
        # Fix B: "foods with sugar above the diabetes limit" links the food "Sugar". When the only food found is the
        # nutrient word itself and the question asks for values above a limit, answer with the list route instead.
        nutrient_toks = {stem(w) for w in NUTRIENT_PROPS}
        above_limit = (nutrient in ("sugarPer100g", "sodiumPer100g") and not dish and food is not None
                       and set(toks(self.label(food))) <= nutrient_toks
                       and has("above", "exceed", "exceeds", "exceeding", "over", "higher than", "more than", "greater than"))

        try:
            if above_limit:
                self.t_above_limit(ctx, nutrient)
            elif unknown_item and yes_no:
                self.t_unknown_item(ctx, unknown, others)
            elif len(conds) >= 2 and has("both", "and") and has("avoid", "unsafe", "should") and not dish and not food:
                self.t_both_conditions(ctx, conds[:2])
            elif has("above", "exceed", "exceeds", "ranked", "rank", "highest") and (nutrient or conds) and not (dish or food) and not has("average", "avg", "group", "groups"):
                self.t_top_nutrient(ctx, nutrient or ("sodiumPer100g" if conds and conds[0] == NR.Hypertension else "sugarPer100g"))
            elif has("guideline", "who", "ada", "nih", "source", "supports", "support", "threshold", "limit", "rule", "rules") and (conds or has("rule", "rules", "guideline")) and not dish and (not food or has("guideline", "source", "supports", "support", "who", "ada", "nih")):
                self.t_rule_info(ctx, conds, food)
            elif has("average", "avg", "per group", "per food group") or (has("which food groups", "food groups")):
                self.t_group_stats(ctx, nutrient)
            elif has("most often", "most common", "appear most", "frequent", "frequently") and has("allergen", "allergens"):
                self.t_allergen_frequency(ctx)
            elif has("safe") and not has("unsafe") and (conds or has("all four", "every condition")) and not dish:
                self.t_safe_for(ctx, conds, "all four" in qn or "every condition" in qn, has("low sugar", "low in sugar"))
            elif dish:
                self.t_dish_profile(ctx, dish)
            elif alg and not conds and not food and has("which", "what", "list") and not self.G.value(alg, NR.triggers):
                self.t_allergen_dishes(ctx, alg)
            elif (conds or alg) and not food and has("which", "what", "list") and has("dishes", "foods", "dish", "food", "contain", "contains", "avoid", "unsafe"):
                self.t_condition_unsafe(ctx, conds[0] if conds else self.G.value(alg, NR.triggers), alg,
                                        hidden=has("although", "without", "hidden", "not in the name", "no nut word", "name"))
            elif food and (nutrient or has("pass", "passes", "unsafe", "safe", "ok", "okay", "allergen", "allergens", "contain", "group", "eat", "avoid", "high", "bad")):
                self.t_food_profile(ctx, food)
            elif food:
                self.t_food_profile(ctx, food)
            elif has("highest", "top", "most", "above", "exceed", "exceeds", "ranked", "rank", "over") and (nutrient or conds):
                prop = nutrient or ("sodiumPer100g" if conds and conds[0] == NR.Hypertension else "sugarPer100g")
                self.t_top_nutrient(ctx, prop)
            elif has("plant", "animal") and has("origin"):
                self.t_origin(ctx, "Plant origin" if "plant" in words else "Animal origin")
            elif alg or conds:
                self.t_condition_unsafe(ctx, conds[0] if conds else self.G.value(alg, NR.triggers), alg,
                                        hidden=has("although", "without", "hidden", "not in the name", "no nut word", "name"))
            elif grp and unknown_item:
                self.t_unknown_item(ctx, unknown, others)
            elif grp:
                self.t_group_members(ctx, grp)
            elif nutrient:
                self.t_top_nutrient(ctx, nutrient)
        except Exception as ex:  # a failing template must never crash the app
            ctx["reason"] = f"retrieval error: {type(ex).__name__}: {ex}"
            ctx["facts"], ctx["paths"] = [], []

        if not ctx["facts"]:
            ctx["sufficient"] = False
            ctx["reason"] = ctx["reason"] or ("No entity from the graph was recognised in the question." if not ents
                                              else "Entities were found but the graph holds no matching facts for this question type.")
            if ctx["type"] == "none" and ents:
                ctx["reason"] = "Entities recognised (" + ", ".join(e["label"] for e in ents[:3]) + ") but no supported question pattern matched."
        else:
            ctx["sufficient"] = True
            ctx["reason"] = ctx["reason"] or "Relevant facts retrieved."
        ctx.pop("_fid")
        return ctx

    # ------------------------------------------------------------------ templates
    def t_dish_profile(self, ctx, dish):
        ctx["type"] = "dish_profile"
        rows = self.q(ctx, f"""SELECT DISTINCT ?ing ?a ?c WHERE {{
            <{dish}> nr:hasIngredient ?ing .
            OPTIONAL {{ ?ing nr:containsAllergen ?a . OPTIONAL {{ ?a nr:triggers ?c }} }} }}""")
        if not rows:
            return
        ings = sorted({r.ing for r in rows}, key=str)
        for ing in ings:
            self.add_fact(ctx, dish, NR.hasIngredient, ing)
        for r in rows:
            if r.a is not None:
                steps = [(dish, NR.hasIngredient, r.ing), (r.ing, NR.containsAllergen, r.a)]
                if r.c is not None:
                    steps.append((r.a, NR.triggers, r.c))
                self.add_path(ctx, steps)
        for a in sorted(set(self.G.objects(dish, NR.containsAllergen)), key=str):
            self.add_fact(ctx, dish, NR.containsAllergen, a)
        for c in sorted(set(self.G.objects(dish, NR.unsafeFor)), key=str):
            self.add_fact(ctx, dish, NR.unsafeFor, c)
        for ing in ings:  # nutrient-based reasons
            for prop, lim, cond, rule in (("sodiumPer100g", self.sodium_limit, NR.Hypertension, "WHO sodium rule"),
                                          ("sugarPer100g", self.sugar_limit, NR.Type2Diabetes, "ADA sugar rule")):
                v = self.G.value(ing, NR[prop])
                if v is not None and float(v) > lim and (ing, NR.unsafeFor, cond) in self.G:
                    self.add_fact(ctx, ing, NR[prop], v, "explicit")
                    self.add_path(ctx, [(dish, NR.hasIngredient, ing), (ing, NR.unsafeFor, cond)])
        if not [r for r in rows if r.a is not None] and not ctx["paths"]:
            ctx["reason"] = "Dish found; none of its ingredients is linked to an allergen or to a nutrient limit in the graph."

    def t_food_profile(self, ctx, food):
        ctx["type"] = "food_profile"
        if self.kind_of(food) is None:
            return
        for prop in ("sugarPer100g", "sodiumPer100g", "caloriesPer100g"):
            self.add_nutrient(ctx, food, prop)
        for p in (NR.belongsToGroup, NR.containsAllergen, NR.unsafeFor):
            for o in sorted(set(self.G.objects(food, p)), key=str):
                self.add_fact(ctx, food, p, o)
        for t in self.G.objects(food, RDF.type):
            if t in (NR.HighSugarFood, NR.HighSodiumFood, NR.LowSugarFood):
                self.add_fact(ctx, food, RDF.type, t)
        for g in self.G.objects(food, NR.belongsToGroup):  # group -> type -> class chain (transitive property)
            cur, chain = g, []
            while True:
                nxt = self.G.value(cur, NR.partOfCategory)
                if nxt is None:
                    break
                chain.append((cur, NR.partOfCategory, nxt))
                cur = nxt
            if chain:
                self.add_path(ctx, [(food, NR.belongsToGroup, g)] + chain)
        for a in self.G.objects(food, NR.containsAllergen):
            for c in self.G.objects(a, NR.triggers):
                self.add_path(ctx, [(food, NR.containsAllergen, a), (a, NR.triggers, c)])
        for r in (URIRef("http://example.org/nutrireason/resource/rule/type2diabetes_sugar_avoid"),
                  URIRef("http://example.org/nutrireason/resource/rule/hypertension_sodium_avoid")):
            self.add_fact(ctx, r, NR.thresholdValue, self.G.value(r, NR.thresholdValue), "explicit")
        if not any(f["predicate"] in ("nr:sugarPer100g", "nr:sodiumPer100g", "nr:containsAllergen", "nr:belongsToGroup") for f in ctx["facts"]):
            ctx["facts"], ctx["paths"] = [], []

    def t_condition_unsafe(self, ctx, cond, alg=None, hidden=False):
        ctx["type"] = "condition_unsafe"
        if cond is None:
            return
        cl = self.label(cond)
        if cond in (NR.NutAllergy, NR.LactoseIntolerance):
            filt = f"FILTER(?a = <{alg}>)" if alg is not None else ""
            name_filter = ""
            rows = self.q(ctx, f"""SELECT DISTINCT ?d ?ing ?a WHERE {{
                ?d a nr:Dish ; nr:hasIngredient ?ing . ?ing nr:containsAllergen ?a . ?a nr:triggers <{cond}> . {filt} }}""")
            items = {}
            for r in rows:
                items.setdefault(r.d, []).append((r.ing, r.a))
            if hidden:
                kw = "nut|almond|pecan|peanut|walnut|cashew|pistachio|hazelnut" if cond == NR.NutAllergy else "milk|cheese|dairy|butter|cream|yogurt|yoghurt"
                items = {d: v for d, v in items.items() if not re.search(kw, self.label(d).lower())}
            ds = sorted(items, key=lambda d: self.label(d))
            ctx["reason"] = f"{len(ds)} dishes are unsafe for {cl} via an allergen-carrying ingredient (showing up to 12)."
            for d in ds[:12]:
                ing, a = items[d][0]
                self.add_path(ctx, [(d, NR.hasIngredient, ing), (ing, NR.containsAllergen, a), (a, NR.triggers, cond)])
                self.add_fact(ctx, d, NR.unsafeFor, cond)
            for r in self.q(ctx, f"""SELECT DISTINCT ?f ?a WHERE {{ ?f nr:containsAllergen ?a . ?a nr:triggers <{cond}> .
                FILTER NOT EXISTS {{ ?f a nr:Dish }} {('FILTER(?a = <%s>)' % alg) if alg is not None else ''} }} LIMIT 5"""):
                self.add_path(ctx, [(r.f, NR.containsAllergen, r.a), (r.a, NR.triggers, cond)])
        else:
            prop, lim = (("sugarPer100g", self.sugar_limit) if cond == NR.Type2Diabetes else ("sodiumPer100g", self.sodium_limit))
            rows = self.q(ctx, f"""SELECT ?f ?v WHERE {{ ?f nr:{prop} ?v ; nr:unsafeFor <{cond}> . FILTER(?v > {lim}) }}
                ORDER BY DESC(?v) LIMIT 12""")
            n = self.q(ctx, f"SELECT (COUNT(DISTINCT ?f) AS ?n) WHERE {{ ?f nr:{prop} ?v . FILTER(?v > {lim}) }}")[0].n
            ctx["reason"] = f"{n} foods exceed the {lim:g} limit for {cl}; the 12 highest are shown."
            for r in rows:
                self.add_fact(ctx, r.f, NR[prop], r.v, "explicit")
                self.add_fact(ctx, r.f, NR.unsafeFor, cond)
                self.add_path(ctx, [(r.f, NR.unsafeFor, cond)])
        self.add_rule_chain(ctx, cond)

    def add_rule_chain(self, ctx, cond):
        for r in self.G.objects(cond, NR.hasRule):
            self.add_fact(ctx, cond, NR.hasRule, r)
            thr = self.G.value(r, NR.thresholdValue)
            if thr is not None:
                self.add_fact(ctx, r, NR.thresholdValue, thr, "explicit")
            act = self.G.value(r, NR.ruleAction)
            if act is not None:
                self.add_fact(ctx, r, NR.ruleAction, act, "explicit")
            for s in self.G.objects(r, NR.hasSource):
                self.add_fact(ctx, r, NR.hasSource, s)
                self.add_path(ctx, [(cond, NR.hasRule, r), (r, NR.hasSource, s)])

    def t_both_conditions(self, ctx, conds):
        ctx["type"] = "both_conditions"
        c1, c2 = conds
        rows = self.q(ctx, f"""SELECT ?f ?s ?n WHERE {{ ?f nr:unsafeFor <{c1}> , <{c2}> ; nr:sugarPer100g ?s ; nr:sodiumPer100g ?n }}
            ORDER BY DESC(?s) LIMIT 10""")
        tot = self.q(ctx, f"SELECT (COUNT(DISTINCT ?f) AS ?n) WHERE {{ ?f nr:unsafeFor <{c1}> , <{c2}> }}")[0].n
        ctx["reason"] = f"{tot} foods are unsafe for both {self.label(c1)} and {self.label(c2)}; top 10 by sugar shown."
        for r in rows:
            self.add_nutrient(ctx, r.f, "sugarPer100g")
            self.add_nutrient(ctx, r.f, "sodiumPer100g")
            self.add_fact(ctx, r.f, NR.unsafeFor, c1)
            self.add_fact(ctx, r.f, NR.unsafeFor, c2)
        for c in conds:
            self.add_rule_chain(ctx, c)

    def t_rule_info(self, ctx, conds, food=None):
        ctx["type"] = "rule_info"
        if food is not None:
            for c in self.G.objects(food, NR.unsafeFor):
                self.add_fact(ctx, food, NR.unsafeFor, c)
                if not conds or c in conds:
                    for r in self.G.objects(c, NR.hasRule):
                        for src in self.G.objects(r, NR.hasSource):
                            self.add_path(ctx, [(food, NR.unsafeFor, c), (c, NR.hasRule, r), (r, NR.hasSource, src)])
        for c in (conds or [NR.NutAllergy, NR.LactoseIntolerance, NR.Type2Diabetes, NR.Hypertension]):
            self.add_rule_chain(ctx, c)

    def t_safe_for(self, ctx, conds, all_four, low_sugar):
        ctx["type"] = "safe_for"
        if all_four or not conds:
            conds = [NR.NutAllergy, NR.LactoseIntolerance, NR.Type2Diabetes, NR.Hypertension]
        nots = " ".join(f"FILTER NOT EXISTS {{ ?f nr:unsafeFor <{c}> }}" for c in conds)
        low = "?f nr:sugarPer100g ?s . FILTER(?s <= 5)" if low_sugar else ""
        rows = self.q(ctx, f"""SELECT DISTINCT ?f ?g WHERE {{ ?f a nr:Food ; nr:belongsToGroup ?g . {low} {nots} }} ORDER BY ?f LIMIT 12""")
        cnt = self.q(ctx, f"""SELECT (COUNT(DISTINCT ?f) AS ?n) WHERE {{ ?f a nr:Food ; nr:belongsToGroup ?g . {low} {nots} }}""")[0].n
        ctx["reason"] = (f"{cnt} foods that the graph classifies (they have a food group) have NO unsafeFor link to "
                         f"{', '.join(self.label(c) for c in conds)}; 12 shown. 'Safe' = absence of an unsafeFor fact (open-world caveat).")
        for r in rows:
            self.add_fact(ctx, r.f, NR.belongsToGroup, r.g)
            for p in ("sugarPer100g", "sodiumPer100g"):
                self.add_nutrient(ctx, r.f, p)
        for c in conds:
            self.add_rule_chain(ctx, c)
        if low_sugar:
            self.add_rule_chain(ctx, NR.Type2Diabetes)  # carries the 'limit_low_sugar' rule (<= 5 g)

    def t_top_nutrient(self, ctx, prop):
        ctx["type"] = "top_nutrient"
        rows = self.q(ctx, f"SELECT ?f ?v WHERE {{ ?f nr:{prop} ?v }} ORDER BY DESC(?v) LIMIT 15")
        for r in rows:
            self.add_fact(ctx, r.f, NR[prop], r.v, "explicit")
        cond = NR.Hypertension if prop == "sodiumPer100g" else NR.Type2Diabetes
        for r in rows:
            if (r.f, NR.unsafeFor, cond) in self.G:
                self.add_fact(ctx, r.f, NR.unsafeFor, cond)
        if prop != "caloriesPer100g":
            self.add_rule_chain(ctx, cond)

    def t_group_stats(self, ctx, nutrient):
        ctx["type"] = "group_stats"
        if nutrient:
            rows = self.q(ctx, f"""SELECT ?g (AVG(?v) AS ?avg) (COUNT(?f) AS ?n) WHERE {{ ?f nr:belongsToGroup ?g ; nr:{nutrient} ?v }}
                GROUP BY ?g ORDER BY DESC(?avg) LIMIT 8""")
            for r in rows:
                ctx["facts"].append({"id": f"F{len(ctx['facts']) + 1}", "subject": self.label(r.g),
                                     "predicate": f"average {nutrient} (aggregate over {r.n} foods)",
                                     "object": f"{float(r.avg):.1f}", "tag": "explicit"})
        else:
            rows = self.q(ctx, """SELECT ?g (COUNT(DISTINCT ?f) AS ?n) WHERE { ?f nr:belongsToGroup ?g ; nr:containsAllergen ?a }
                GROUP BY ?g ORDER BY DESC(?n) LIMIT 8""")
            for r in rows:
                ctx["facts"].append({"id": f"F{len(ctx['facts']) + 1}", "subject": self.label(r.g),
                                     "predicate": "number of foods linked to an allergen (aggregate)", "object": str(r.n), "tag": "explicit"})
        ctx["reason"] = "Aggregates computed by SPARQL GROUP BY over explicit facts."

    def t_allergen_frequency(self, ctx):
        ctx["type"] = "allergen_frequency"
        rows = self.q(ctx, """SELECT ?a (COUNT(DISTINCT ?d) AS ?n) WHERE { ?d a nr:Dish ; nr:containsAllergen ?a }
            GROUP BY ?a ORDER BY DESC(?n) LIMIT 8""")
        for r in rows:
            ctx["facts"].append({"id": f"F{len(ctx['facts']) + 1}", "subject": self.label(r.a),
                                 "predicate": "number of dishes containing this allergen (incl. inherited from ingredients)",
                                 "object": str(r.n), "tag": "inferred"})
        ctx["reason"] = "Counts include allergens inherited from ingredients (property chain, inferred) - tagged inferred."

    def t_origin(self, ctx, cls_label):
        ctx["type"] = "origin_foods"
        rows = self.q(ctx, f"""SELECT DISTINCT ?f ?g ?t ?c WHERE {{ ?f nr:belongsToGroup ?g ; nr:containsAllergen ?a .
            ?g nr:partOfCategory ?t . ?t nr:partOfCategory ?c . ?c rdfs:label "{cls_label}"@en }} ORDER BY ?f LIMIT 10""")
        for r in rows:
            self.add_path(ctx, [(r.f, NR.belongsToGroup, r.g), (r.g, NR.partOfCategory, r.t), (r.t, NR.partOfCategory, r.c)])
            for a in list(self.G.objects(r.f, NR.containsAllergen))[:1]:
                self.add_fact(ctx, r.f, NR.containsAllergen, a)

    def t_allergen_dishes(self, ctx, alg):
        ctx["type"] = "allergen_dishes"
        rows = self.q(ctx, f"""SELECT DISTINCT ?d ?ing WHERE {{ ?d a nr:Dish ; nr:hasIngredient ?ing . ?ing nr:containsAllergen <{alg}> }}
            ORDER BY ?d LIMIT 12""")
        n = self.q(ctx, f"SELECT (COUNT(DISTINCT ?d) AS ?n) WHERE {{ ?d a nr:Dish ; nr:containsAllergen <{alg}> }}")[0].n
        ctx["reason"] = f"{n} dishes contain {self.label(alg)} (own or via an ingredient); up to 12 shown."
        seen = set()
        for r in rows:
            if r.d in seen:
                continue
            seen.add(r.d)
            self.add_path(ctx, [(r.d, NR.hasIngredient, r.ing), (r.ing, NR.containsAllergen, alg)])

    def t_unknown_item(self, ctx, unknown, others):
        """Fix A. Return no facts on purpose, so sufficient = False and the LLM is told to decline."""
        ctx["type"] = "unknown_item"
        found = ", ".join(f"{e['label']} ({e['kind']})" for e in others)
        ctx["reason"] = ("The item named in the question is not in the knowledge graph (unmatched words: "
                         + ", ".join(f"'{w}'" for w in unknown) + ")."
                         + (f" Only {found} matched, which is not the item asked about." if found else ""))

    def t_above_limit(self, ctx, prop):
        """Fix B. Foods whose nutrient value is above the rule threshold, highest first, with exact values.
        The limit is read from the rule node (22.5 g sugar / 600 mg sodium), not hard-coded."""
        ctx["type"] = "above_limit"
        if prop == "sugarPer100g":
            lim, cond, unit, name = self.sugar_limit, NR.Type2Diabetes, "g", "sugar"
        else:
            lim, cond, unit, name = self.sodium_limit, NR.Hypertension, "mg", "sodium"
        rows = self.q(ctx, f"""SELECT ?f ?v WHERE {{ ?f nr:{prop} ?v . FILTER(?v > {lim}) }}
                               ORDER BY DESC(?v) LIMIT 15""")
        n = self.q(ctx, f"SELECT (COUNT(DISTINCT ?f) AS ?n) WHERE {{ ?f nr:{prop} ?v . FILTER(?v > {lim}) }}")[0].n
        ctx["reason"] = (f"{n} foods have {name} above the {lim:g} {unit} per 100 g limit for {self.label(cond)}; "
                         f"the 15 highest are shown with exact values.")
        for r in rows:
            self.add_fact(ctx, r.f, NR[prop], r.v, "explicit")
            if (r.f, NR.unsafeFor, cond) in self.G:
                self.add_fact(ctx, r.f, NR.unsafeFor, cond)
        self.add_rule_chain(ctx, cond)

    def t_group_members(self, ctx, grp):
        ctx["type"] = "group_members"
        rows = self.q(ctx, f"SELECT ?f WHERE {{ ?f nr:belongsToGroup <{grp}> }} ORDER BY ?f LIMIT 10")
        for r in rows:
            self.add_fact(ctx, r.f, NR.belongsToGroup, grp)


if __name__ == "__main__":
    import sys, json
    r = KGRetriever()
    out = r.retrieve(" ".join(sys.argv[1:]) or "Why is Almond Cookies unsafe for anyone?")
    out.pop("queries")
    print(json.dumps(out, indent=2))
