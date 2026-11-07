# NutriReason – Data Cleaning and Transformation (Iteration 1)

Team krr-08-nutrireason · AI-3001 Knowledge Representation & Reasoning

## 1. Overview

We use four datasets. One Python script, `build_kg.py` (pandas + rdflib), cleans them and turns them into RDF triples in Turtle format.

| Dataset | Source | What it gives us |
|---|---|---|
| D1 | Kaggle – Food: Allergens and Allergies | Food groups, types, classes and which allergy a food is linked to |
| D2 | Kaggle – Food Ingredients and Allergens | Dishes, their ingredients and their allergens |
| D3 | USDA National Nutrient Database | Calories, sodium and sugar for each food |
| D4 | Curated dietary rules | Rules for each health condition, with the guideline that supports it |

Run command:

```
python build_kg.py --data-dir data --out abox.ttl --tbox ontology/nutrireason_tbox.ttl
```

The script processes the datasets in this order: **D3 → D1 → D2 → D4**. D3 goes first because it creates the food nodes with nutrient values. D1 then adds groups and allergens to those nodes. D2 uses the finished food list to find its ingredients. D4 is separate and goes last.

## 2. Cleaning steps used for all four datasets

1. **Read everything as text.** Every column is read as a string (UTF-8, with the byte-order mark removed). This stops IDs and values like "None" or "N/A" from being changed by accident.
2. **Fix spaces.** Extra spaces are removed from column names and cells.
3. **Find missing values.** These are all treated as missing: an empty cell, `None`, `N/A`, `NA`, `NaN`, `null` and `-` (any letter case).
4. **Remove duplicates.** Exact duplicate rows are dropped first. Then each dataset is checked on its own key:
   - D1: the food name, after plural folding (so "Almonds" and "Almond" count as one)
   - D2: the dish name
   - D3: the `ID`, then the description
   - D4: exact duplicates only
5. **Check columns.** If a required column is missing, the script stops with a clear message.
6. **Log the changes.** The script prints how many rows it read and dropped, so we can quote the numbers.

## 3. Names to URIs: lower-case ASCII slugs

Every name becomes the last part of a URI in the same way:

1. Remove accents and any non-ASCII characters (`Crème Brûlée` becomes `Creme Brulee`).
2. Change everything to lower case.
3. Replace every group of characters that is not a letter or digit with one underscore.
4. Remove underscores at the start and end.

| Original value | Slug |
|---|---|
| `BUTTER,WITH SALT` | `butter_with_salt` |
| `Almond Cookies` | `almond_cookies` |
| `Nut and seed` | `nut_and_seed` |
| `Type2Diabetes` + `Sugar` + `avoid` | `type2diabetes_sugar_avoid` |

For matching names between datasets, the script also uses a simple plural fix: it removes a final "s" (`almonds` becomes `almond`) and turns words ending in "oes" into their singular form (`potatoes` becomes `potato`). Words ending in "ss", "us" or "is" are left alone. This fix is only used for matching and for ingredient URIs. USDA food URIs use the full description.

## 4. What we do with each dataset

### D3 – USDA nutrients (creates the `nr:Food` nodes)
- Calories, Sodium and Sugar are converted to numbers.
- A row is dropped if it has no description, or if calories, sodium or sugar is missing or negative.
- Duplicates are removed by `ID` and then by description.
- Each food gets a label (`BUTTER,WITH SALT` becomes "Butter, With Salt") and three values: `caloriesPer100g`, `sodiumPer100g` and `sugarPer100g`. Units are kcal, mg and g per 100 g. They are stored as `xsd:decimal` with two decimals.
- The USDA `ID` is kept as `dct:identifier`.
- Protein, fat and carbohydrate are not loaded, because none of our competency questions use them.
- The script also builds a list that links each food's first word (for example "butter") to its food nodes. D1 and D2 use this list.

### D1 – Allergens and food taxonomy
- Rows with no food or no group are dropped.
- `Class`, `Type` and `Group` become `nr:FoodClass`, `nr:FoodType` and `nr:FoodGroup` nodes.
- They are linked with `partOfCategory`: group → type → class. In the ontology this property is transitive, so a group is also linked to its class.
- The `Allergy` column is split on "/" (for example "Milk allergy / Lactose intolerance"). The allergen is chosen in this order:
  1. a keyword in the food name (Almond → `alg:almond`);
  2. if nothing was found, a keyword in the allergy label (nut → general nut allergen, milk or lactose → dairy, gluten → wheat, legume → soy);
  3. if still nothing, a new general allergen named from the label (for example "Broccoli allergy" → `alg:broccoli`).
- Linking to D3: the D1 food is matched to USDA foods by its first word (Butter matches `BUTTER,WITH SALT`). Every matching USDA food gets the group and the allergens. If there is no match, a new standalone `food:` node is created.

### D2 – Dishes and ingredients
- Each dish becomes an `nr:Dish`.
- Ingredients are taken from `Main Ingredient`, `Sweetener`, `Fat/Oil` and the comma-separated `Seasoning`. Missing values are removed, and an ingredient is only counted once per dish.
- Each ingredient name is looked up in the food list:
  - **One match:** we reuse that food node and also mark it as `nr:Ingredient`.
  - **Several matches:** we create a new ingredient node (`ing:`) with the average of the matching USDA values, and add a comment that says so.
  - **No match:** we create a plain ingredient node with no nutrient values.
- Ingredient allergens come from the D1 link and from simple keywords (flour → wheat, butter or cheese → dairy, and so on).
- The dish's own `Allergens` column is used as a second check. If a listed allergen is not already explained by an ingredient, it is added directly to the dish. All other dish allergens come from the ingredients through the ontology's property chain.
- The `Prediction` column is dropped. It only repeats that allergens are present.

### D4 – Dietary rules
- The condition, guideline and nutrient text are mapped to the named individuals of the ontology (`nr:Type2Diabetes`, `nr:ADA`, `nr:Sugar` and so on). Unknown values are skipped with a warning.
- Each row becomes one `nr:DietaryRule`. It is linked to its condition with `hasRule` and to its guideline with `hasSource`. It also gets `ruleAction` and, for numeric rows, `thresholdValue`.
- Allergen rows have no number. The allergen class from the `ThresholdValue` column is stored with `restrictsAllergenClass`.
- `ThresholdUnit` is not loaded. The units (g or mg per 100 g) are written in the ontology comments.

## 5. URI design

| Entity | Pattern | Example |
|---|---|---|
| Vocabulary (T-Box) | `http://example.org/nutrireason#Name` | `nr:Dish`, `nr:NutAllergy`, `nr:ADA` |
| Food (D3, or D1 only) | `http://example.org/nutrireason/resource/food/<slug>` | `food:cheese_cheddar` |
| Dish (D2) | `…/resource/dish/<slug>` | `dish:almond_cookies` |
| Ingredient (D2) | `…/resource/ingredient/<slug>` | `ing:parmesan_cheese` |
| Food group, type, class | `…/resource/group/`, `type/`, `class/` | `grp:dairy`, `typ:nut_and_seed`, `cls:plant_origin` |
| Allergen | `…/resource/allergen/<key>` | `alg:almond` |
| Dietary rule | `…/resource/rule/<condition>_<nutrient>_<action>` | `rule:hypertension_sodium_avoid` |

- Conditions, nutrients and guidelines (such as `nr:Hypertension`, `nr:Sodium`, `nr:WHO`) are part of the model, so they live in the `nr:` namespace.
- Because slugs are built from the cleaned name, the same food in two datasets gets the same URI when the script can match them.
- Every instance has a `dct:source` value (D1, D2, D3 or D4), so we can trace where it came from.

## 6. Example

For the D3 row `1001,"BUTTER,WITH SALT",717,…,714,0.06`, plus the D1 row for Butter, the script writes:

```turtle
food:butter_with_salt a nr:Food ;
    rdfs:label "Butter, With Salt"@en ;
    nr:caloriesPer100g 717.00 ;
    nr:sodiumPer100g 714.00 ;
    nr:sugarPer100g 0.06 ;
    nr:belongsToGroup grp:dairy ;
    nr:containsAllergen alg:dairy ;
    dct:identifier "1001" ;
    dct:source "D3", "D1" .
```

## 7. Limitations

- Allergens are found with a simple keyword list. For example, "peanut butter" gets both peanut and dairy, and "Caesar dressing" gets none. The `ALLERGENS` list in the script can be extended.
- A D1 food is linked to every USDA food that starts with the same word, so "Almond" is linked to almond butter and other almond foods.
- Some D1 allergy labels have no known keyword and become general allergens.
- Ingredients with no USDA match (for example salt, sugar and flour) have no sodium or sugar value.
- When an ingredient matches several USDA foods, its values are an average, and a comment on the node says so.
- Dishes have no nutrient values of their own.