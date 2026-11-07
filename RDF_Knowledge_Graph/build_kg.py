#!/usr/bin/env python3
"""
NutriReason - CSV (D1-D4) -> RDF/Turtle A-Box builder.

Usage:
    python build_kg.py --data-dir data --out abox.ttl [--tbox ontology/nutrireason_tbox.ttl]

Input files in --data-dir:
    D1_allergens.csv  Class,Type,Group,Food,Allergy
    D2_ingredients.csv     Food Product,Main Ingredient,Sweetener,Fat/Oil,Seasoning,Allergens,Prediction
    D3_usda.csv       ID,Description,Calories,Protein,TotalFat,Carbohydrate,Sodium,Sugar
    D4_rules.csv      Condition,RestrictedNutrient,ThresholdValue,ThresholdUnit,RuleAction,GuidelineSource

Requires: pandas, rdflib  (pip install pandas rdflib)
"""
import argparse
import logging
import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, XSD

log = logging.getLogger("nutrireason")

# --------------------------------------------------------------------------- #
# Namespaces / URI design
# --------------------------------------------------------------------------- #
NR = Namespace("http://example.org/nutrireason#")          # T-Box vocabulary
BASE = "http://example.org/nutrireason/resource/"          # A-Box instances
FOOD = Namespace(BASE + "food/")
DISH = Namespace(BASE + "dish/")
ING = Namespace(BASE + "ingredient/")
GRP = Namespace(BASE + "group/")
TYP = Namespace(BASE + "type/")
CLS = Namespace(BASE + "class/")
ALG = Namespace(BASE + "allergen/")
RULE = Namespace(BASE + "rule/")

NULLS = {"", "none", "n/a", "na", "nan", "null", "-"}

# Allergen vocabulary: key -> (label, class, whole-word keywords)
ALLERGENS = {
    "almond":     ("Almond", NR.TreeNutAllergen, ["almond"]),
    "walnut":     ("Walnut", NR.TreeNutAllergen, ["walnut"]),
    "cashew":     ("Cashew", NR.TreeNutAllergen, ["cashew"]),
    "pecan":      ("Pecan", NR.TreeNutAllergen, ["pecan"]),
    "hazelnut":   ("Hazelnut", NR.TreeNutAllergen, ["hazelnut"]),
    "pistachio":  ("Pistachio", NR.TreeNutAllergen, ["pistachio"]),
    "pine_nut":   ("Pine nut", NR.TreeNutAllergen, ["pine nut"]),
    "peanut":     ("Peanut", NR.PeanutAllergen, ["peanut"]),
    "nut_generic": ("Nut (unspecified)", NR.NutAllergen, ["nut", "nuts"]),
    "wheat":      ("Wheat / Gluten", NR.GlutenAllergen,
                   ["wheat", "flour", "noodle", "pasta", "barley", "bread", "rye", "gluten"]),
    "dairy":      ("Dairy", NR.DairyAllergen,
                   ["dairy", "milk", "cheese", "butter", "cream", "yogurt", "mozzarella",
                    "parmesan", "cheddar", "feta"]),
    "chicken":    ("Chicken", NR.Allergen, ["chicken"]),
    "celery":     ("Celery", NR.Allergen, ["celery"]),
    "soy":        ("Soy / Legume", NR.Allergen, ["soy", "soybean", "tofu"]),
}
# Fallback: D1 'Allergy' label fragment -> allergen key
ALLERGY_LABEL_TO_KEY = [("nut", "nut_generic"), ("milk", "dairy"), ("lactose", "dairy"),
                        ("gluten", "wheat"), ("legume", "soy")]

CONDITIONS = {"nutallergy": NR.NutAllergy, "lactoseintolerance": NR.LactoseIntolerance,
              "type2diabetes": NR.Type2Diabetes, "hypertension": NR.Hypertension}
NUTRIENTS = {"sugar": NR.Sugar, "sodium": NR.Sodium, "calories": NR.Calories}
GUIDELINES = {"who": NR.WHO, "ada": NR.ADA, "nih": NR.NIH}
ALLERGEN_CLASSES = {"nutallergen": NR.NutAllergen, "dairyallergen": NR.DairyAllergen,
                    "glutenallergen": NR.GlutenAllergen, "treenutallergen": NR.TreeNutAllergen,
                    "peanutallergen": NR.PeanutAllergen}


# --------------------------------------------------------------------------- #
# String helpers
# --------------------------------------------------------------------------- #
def clean(text) -> str:
    """Trim and collapse whitespace."""
    return re.sub(r"\s+", " ", str(text)).strip()


def is_null(value) -> bool:
    return pd.isna(value) or clean(value).lower() in NULLS


def slug(text) -> str:
    """URI-safe, lower-case, ASCII, underscore-separated."""
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")


def singular(word: str) -> str:
    """Crude plural folding for matching keys (almonds -> almond)."""
    if word.endswith("oes"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def pretty(text: str) -> str:
    """'BUTTER,WITH SALT' -> 'Butter, With Salt'."""
    return re.sub(r"\s*,\s*", ", ", clean(text)).title()


def dec(x) -> Literal:
    return Literal(Decimal(str(x)).quantize(Decimal("0.01"), ROUND_HALF_UP), datatype=XSD.decimal)


def load_csv(path: Path, required: list[str]) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df.columns = [clean(c) for c in df.columns]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name}: missing columns {missing}")
    for c in df.columns:
        df[c] = df[c].map(clean)
    n0 = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    log.info("%s: %d rows read, %d exact duplicates dropped", path.name, n0, n0 - len(df))
    return df


def match_allergens(text: str) -> list[str]:
    t = text.lower()
    keys = []
    for key, (_, _, kws) in ALLERGENS.items():
        if any(re.search(rf"\b{re.escape(kw)}s?\b", t) for kw in kws):
            keys.append(key)
    return keys


def allergen_node(g: Graph, key: str, label: str | None = None, cls=None) -> URIRef:
    if key in ALLERGENS:
        lab, c, _ = ALLERGENS[key]
    else:
        lab, c = label or key.replace("_", " ").title(), cls or NR.Allergen
    uri = ALG[key]
    if (uri, RDF.type, None) not in g:
        g.add((uri, RDF.type, c))
        g.add((uri, RDFS.label, Literal(lab, lang="en")))
    return uri


def tag(g: Graph, uri: URIRef, source: str):
    g.add((uri, DCTERMS.source, Literal(source)))


# --------------------------------------------------------------------------- #
# D3  USDA nutrients -> nr:Food
# --------------------------------------------------------------------------- #
def build_d3(g: Graph, df: pd.DataFrame, food_index: dict):
    for col in ["Calories", "Sodium", "Sugar"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    n0 = len(df)
    df = df.dropna(subset=["Description", "Calories", "Sodium", "Sugar"])
    df = df[(df[["Calories", "Sodium", "Sugar"]] >= 0).all(axis=1)]
    df = df[df["Description"] != ""]
    df = df.assign(_slug=df["Description"].map(slug))
    df = df.drop_duplicates(subset="ID").drop_duplicates(subset="_slug")
    log.info("D3: %d rows kept (%d dropped: missing/negative/duplicate)", len(df), n0 - len(df))

    for _, r in df.iterrows():
        uri = FOOD[r["_slug"]]
        g.add((uri, RDF.type, NR.Food))
        g.add((uri, RDFS.label, Literal(pretty(r["Description"]), lang="en")))
        g.add((uri, NR.caloriesPer100g, dec(r["Calories"])))
        g.add((uri, NR.sodiumPer100g, dec(r["Sodium"])))
        g.add((uri, NR.sugarPer100g, dec(r["Sugar"])))
        g.add((uri, DCTERMS.identifier, Literal(str(r["ID"]))))
        tag(g, uri, "D3")
        head = singular(slug(r["Description"].split(",")[0]))
        food_index.setdefault(head, [])
        if uri not in food_index[head]:
            food_index[head].append(uri)


# --------------------------------------------------------------------------- #
# D1  Allergen / taxonomy -> groups, types, classes, allergen links
# --------------------------------------------------------------------------- #
def build_d1(g: Graph, df: pd.DataFrame, food_index: dict, d1_info: dict):
    df = df[(df["Food"] != "") & (df["Group"] != "")]
    df = df.assign(_k=df["Food"].map(lambda s: singular(slug(s)))).drop_duplicates(subset="_k")
    log.info("D1: %d distinct foods", len(df))

    for _, r in df.iterrows():
        cls_u, typ_u, grp_u = CLS[slug(r["Class"])], TYP[slug(r["Type"])], GRP[slug(r["Group"])]
        for u, c, lab in [(cls_u, NR.FoodClass, r["Class"]), (typ_u, NR.FoodType, r["Type"]),
                          (grp_u, NR.FoodGroup, r["Group"])]:
            g.add((u, RDF.type, c))
            g.add((u, RDFS.label, Literal(lab, lang="en")))
        g.add((grp_u, NR.partOfCategory, typ_u))     # Group -> Type
        g.add((typ_u, NR.partOfCategory, cls_u))     # Type  -> Class (transitive => Group -> Class)

        # allergen keys: by food name first, then by the Allergy label
        keys = set(match_allergens(r["Food"]))
        for frag in re.split(r"\s*/\s*", r["Allergy"]):
            if is_null(frag):
                continue
            if not keys:
                for part, key in ALLERGY_LABEL_TO_KEY:
                    if part in frag.lower():
                        keys.add(key)
                if not keys:  # e.g. 'Broccoli allergy' -> dynamic allergen
                    name = re.sub(r"(?i)\ballerg(y|ies)\b", "", frag).strip()
                    k = slug(name)
                    allergen_node(g, k, label=name.title())
                    keys.add(k)
        key = r["_k"]
        d1_info[key] = (grp_u, keys)

        targets = food_index.get(key)
        if not targets:                              # no USDA match -> standalone D1 node
            uri = FOOD[slug(r["Food"])]
            g.add((uri, RDF.type, NR.Food))
            g.add((uri, RDFS.label, Literal(r["Food"], lang="en")))
            tag(g, uri, "D1")
            food_index[key] = targets = [uri]
        for uri in targets:
            g.add((uri, NR.belongsToGroup, grp_u))
            for k in keys:
                g.add((uri, NR.containsAllergen, allergen_node(g, k)))
            tag(g, uri, "D1")


# --------------------------------------------------------------------------- #
# D2  Dishes and ingredients
# --------------------------------------------------------------------------- #
def ingredient_node(g: Graph, name: str, food_index: dict, d1_info: dict) -> URIRef:
    key = singular(slug(name))
    hits = food_index.get(key, [])
    if len(hits) == 1:                               # unambiguous: reuse the food node
        uri = hits[0]
        g.add((uri, RDF.type, NR.Ingredient))
    else:
        uri = ING[key]
        g.add((uri, RDF.type, NR.Ingredient))
        g.add((uri, RDFS.label, Literal(name[:1].upper() + name[1:], lang="en")))
        tag(g, uri, "D2")
        if len(hits) > 1:                            # ambiguous: average the USDA entries
            for prop in (NR.sugarPer100g, NR.sodiumPer100g, NR.caloriesPer100g):
                vals = [Decimal(str(g.value(h, prop))) for h in hits if g.value(h, prop) is not None]
                if vals:
                    g.add((uri, prop, dec(sum(vals) / len(vals))))
            g.add((uri, RDFS.comment,
                   Literal(f"Nutrient values are the mean of {len(hits)} USDA entries (D3).")))
        if key in d1_info:
            g.add((uri, NR.belongsToGroup, d1_info[key][0]))
            for k in d1_info[key][1]:
                g.add((uri, NR.containsAllergen, allergen_node(g, k)))
    for k in match_allergens(name):                  # keyword-derived allergens
        g.add((uri, NR.containsAllergen, allergen_node(g, k)))
    return uri


def build_d2(g: Graph, df: pd.DataFrame, food_index: dict, d1_info: dict):
    df = df[df["Food Product"] != ""]
    df = df.assign(_s=df["Food Product"].map(slug)).drop_duplicates(subset="_s")
    log.info("D2: %d distinct dishes", len(df))

    for _, r in df.iterrows():
        dish = DISH[r["_s"]]
        g.add((dish, RDF.type, NR.Dish))
        g.add((dish, RDFS.label, Literal(r["Food Product"], lang="en")))
        tag(g, dish, "D2")

        names = [r[c] for c in ("Main Ingredient", "Sweetener", "Fat/Oil") if not is_null(r[c])]
        names += [clean(s) for s in r["Seasoning"].split(",") if not is_null(s)]
        seen, derived = set(), set()
        for n in names:
            if n.lower() in seen:
                continue
            seen.add(n.lower())
            ing = ingredient_node(g, n, food_index, d1_info)
            g.add((dish, NR.hasIngredient, ing))
            derived |= {o for o in g.objects(ing, NR.containsAllergen)}

        # D2 'Allergens' not explained by any ingredient -> assert at dish level
        for tok in [clean(t) for t in r["Allergens"].split(",") if not is_null(t)]:
            keys = match_allergens(tok) or [slug(tok)]
            for k in keys:
                node = allergen_node(g, k, label=tok.title())
                if node not in derived:
                    g.add((dish, NR.containsAllergen, node))
                    log.info("D2: %s -> allergen '%s' asserted at dish level", r["Food Product"], tok)


# --------------------------------------------------------------------------- #
# D4  Dietary rules
# --------------------------------------------------------------------------- #
def build_d4(g: Graph, df: pd.DataFrame):
    for _, r in df.iterrows():
        cond = CONDITIONS.get(slug(r["Condition"]).replace("_", ""))
        guide = GUIDELINES.get(r["GuidelineSource"].lower())
        if cond is None or guide is None:
            log.warning("D4: skipping unknown condition/guideline: %s", dict(r))
            continue
        rule = RULE[slug(f'{r["Condition"]}_{r["RestrictedNutrient"]}_{r["RuleAction"]}')]
        g.add((rule, RDF.type, NR.DietaryRule))
        g.add((rule, RDFS.label, Literal(f'{r["Condition"]} / {r["RestrictedNutrient"]} / {r["RuleAction"]}')))
        g.add((cond, NR.hasRule, rule))              # appliesTo is the inverse; not asserted
        g.add((rule, NR.hasSource, guide))
        g.add((rule, NR.ruleAction, Literal(r["RuleAction"], datatype=XSD.string)))
        nut = NUTRIENTS.get(r["RestrictedNutrient"].lower())
        if nut is not None:
            g.add((rule, NR.restrictsNutrient, nut))
        elif r["RestrictedNutrient"].lower() == "allergen":
            acls = ALLERGEN_CLASSES.get(r["ThresholdValue"].lower())
            if acls is not None:
                g.add((rule, NR.restrictsAllergenClass, acls))
        try:
            g.add((rule, NR.thresholdValue, dec(float(r["ThresholdValue"]))))
        except ValueError:
            pass                                      # 'NutAllergen' etc. - not numeric
        tag(g, rule, "D4")


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--out", default="abox.ttl")
    ap.add_argument("--tbox", default=None, help="optional T-Box .ttl to merge for a sanity check")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    d = Path(a.data_dir)

    d1 = load_csv(d / "D1_allergens.csv", ["Class", "Type", "Group", "Food", "Allergy"])
    d2 = load_csv(d / "D2_ingredients.csv", ["Food Product", "Main Ingredient", "Sweetener", "Fat/Oil",
                                        "Seasoning", "Allergens"])
    d3 = load_csv(d / "D3_usda.csv", ["ID", "Description", "Calories", "Sodium", "Sugar"])
    d4 = load_csv(d / "D4_rules.csv", ["Condition", "RestrictedNutrient", "ThresholdValue",
                                       "ThresholdUnit", "RuleAction", "GuidelineSource"])

    g = Graph()
    for p, ns in [("nr", NR), ("food", FOOD), ("dish", DISH), ("ing", ING), ("grp", GRP),
                  ("typ", TYP), ("cls", CLS), ("alg", ALG), ("rule", RULE),
                  ("owl", OWL), ("rdfs", RDFS), ("xsd", XSD), ("dct", DCTERMS)]:
        g.bind(p, ns)

    food_index, d1_info = {}, {}
    build_d3(g, d3, food_index)      # 1. nutrient-bearing food nodes
    build_d1(g, d1, food_index, d1_info)   # 2. taxonomy + allergens (merged onto D3 nodes)
    build_d2(g, d2, food_index, d1_info)   # 3. dishes + ingredients
    build_d4(g, d4)                  # 4. dietary rules

    g.serialize(destination=a.out, format="turtle")
    print(f"Wrote {a.out}: {len(g)} triples")

    if a.tbox:
        merged = Graph().parse(a.tbox, format="turtle") + g
        print(f"T-Box + A-Box parse OK: {len(merged)} triples total")


if __name__ == "__main__":
    main()
