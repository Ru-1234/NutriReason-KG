# NutriReason – Data Cleaning & Transformation Description (Iteration 1)

Team krr-08-nutrireason · AI-3001 KRR

Script: `build_kg.py` (pandas + rdflib). Run: `python build_kg.py --data-dir data --out abox.ttl --tbox ontology/nutrireason_tbox.ttl`

## 1. Common cleaning steps (all four datasets)
1. Read every column as text (`dtype=str`, UTF-8 with BOM stripped) so IDs and "None"/"N/A" are not silently converted.
2. Trim and collapse whitespace in headers and cells.
3. Treat `""`, `None`, `N/A`, `NaN`, `null`, `-` as missing values.
4. Drop exact duplicate rows, then duplicates on the dataset's natural key (see below).
5. Validate required columns; fail early with a clear message if one is missing.
6. Log every drop/assertion so the progress report can quote the counts.

## 2. Dataset-specific steps

**D1 – Food: Allergens and Allergies (taxonomy + allergy links)**
- Dedupe on the singularised food name (`Almonds`/`Almond`).
- `Class`, `Type`, `Group` become `nr:FoodClass`, `nr:FoodType`, `nr:FoodGroup` individuals. Links: Group `partOfCategory` Type, Type `partOfCategory` Class (transitive in the T-Box, so Group → Class is inferred).
- `Allergy` is split on `/` ("Milk allergy / Lactose intolerance"). Each part maps to an allergen individual: first by keyword in the food name (Almond → `alg:almond`), otherwise by label fragment (nut → `nut_generic`, milk/lactose → `dairy`, gluten → `wheat`, legume → `soy`), otherwise a new generic allergen (e.g. "Broccoli allergy" → `alg:broccoli`).
- The D1 food is linked to D3 by head-word match (Butter ↔ `BUTTER,WITH SALT`). If D3 has matches, the group and allergens are copied onto those D3 nodes and no duplicate node is created. If not (Almond, Barley, Soybean), a standalone `food:` node is created.

**D2 – Food Ingredients and Allergens (dishes)**
- Dedupe on dish-name slug.
- Ingredients come from `Main Ingredient`, `Sweetener`, `Fat/Oil` and the comma-separated `Seasoning`; "None" is dropped and ingredients are de-duplicated per dish.
- Each ingredient is resolved against the food index. One match reuses that food node (and adds type `nr:Ingredient`); several matches create `ing:` with the mean of the USDA values and a comment saying so; no match creates a plain `ing:` node.
- Allergens on ingredients come from the D1 link plus whole-word keyword rules (flour → wheat, butter/cheese → dairy, etc.).
- The dish `Allergens` column is used as a check: any listed allergen not already derived from an ingredient is asserted on the dish directly (e.g. Wheat and Celery for Chicken Noodle Soup). Everything else is left for the property chain to infer.
- `Prediction` is dropped (it only restates that allergens are present).

**D3 – USDA nutrients**
- Coerce Calories/Sodium/Sugar to numbers; drop rows with missing or negative values; dedupe on `ID`, then on description slug.
- Label: `BUTTER,WITH SALT` → "Butter, With Salt". Values stored as `xsd:decimal` (2 dp): sugar in g, sodium in mg, calories in kcal, all per 100 g. The USDA `ID` is kept as `dct:identifier`.
- Protein, fat and carbohydrate are not used by any CQ and are not loaded.

**D4 – Dietary rules**
- Condition, guideline and nutrient strings are mapped to the T-Box individuals (`nr:Type2Diabetes`, `nr:ADA`, `nr:Sugar` …); unknown values are skipped with a warning.
- One `nr:DietaryRule` per row, linked with `hasRule` (the inverse `appliesTo` is inferred, not stored). Numeric thresholds become `nr:thresholdValue`; `RuleAction` becomes `nr:ruleAction`.
- Allergen rows (`RestrictedNutrient = Allergen`) have no numeric threshold, so the allergen class goes in the annotation property `nr:restrictsAllergenClass`.

## 3. URI design

| Entity | Pattern | Example |
|---|---|---|
| Vocabulary (T-Box) | `http://example.org/nutrireason#Name` | `nr:Dish`, `nr:NutAllergy`, `nr:ADA` |
| Food (D1/D3) | `…/resource/food/<slug>` | `food:cheese_cheddar` |
| Dish (D2) | `…/resource/dish/<slug>` | `dish:almond_cookies` |
| Ingredient (D2, unmatched) | `…/resource/ingredient/<slug>` | `ing:parmesan_cheese` |
| Food group / type / class | `…/resource/group/`, `type/`, `class/` | `grp:dairy`, `typ:nut_and_seed`, `cls:plant_origin` |
| Allergen | `…/resource/allergen/<key>` | `alg:almond` |
| Dietary rule | `…/resource/rule/<condition>_<nutrient>_<action>` | `rule:hypertension_sodium_avoid` |

Rules: slugs are lower-case ASCII with `_`; the URI is built from the cleaned name so the same entity from two datasets gets one URI; schema-level individuals (conditions, nutrients, guidelines) live in `nr:` because they are part of the model; every instance carries `dct:source` (D1–D4) for traceability.

## 4. Known limitations (mention in the report)
- Allergen keyword rules are simple (e.g. "peanut butter" gets both peanut and dairy; Caesar dressing gets none). Extend `ALLERGENS` or add a curated override CSV for the full dataset.
- Ingredients with several USDA matches get averaged values, flagged by `rdfs:comment`.
- Ingredients with no USDA match (salt, sugar, flour) have no sodium/sugar, so they cannot trigger the nutrient rules.
- The 5-row samples give 226 A-Box triples (622 with the T-Box); the full Kaggle/USDA files will clear the 500-triple minimum easily.
