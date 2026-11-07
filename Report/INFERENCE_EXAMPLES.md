# Inference examples (Explicit Facts -> Rule / Schema Knowledge -> Inferred Fact)

All three were produced by running `Ontology/rules_graphdb.ru` in GraphDB (SPARQL -> Update) and then the query shown.
Before the rules run, each query returns **0 rows** (see `Results/*_BEFORE_rules.csv`). After it, they return rows.
The rules script adds 7,673 triples (42,478 -> 50,151 in my offline check; use your own GraphDB numbers in the report).

## Example 1 - Ingredient allergen inheritance (query: `INF1_allergen_inheritance.rq`)
| Step | Content |
|---|---|
| Explicit facts (A-Box) | `dish:chicken_satay nr:hasIngredient <Peanut butter>` ; `<Peanut butter> nr:containsAllergen alg:peanut` ; `alg:peanut a nr:PeanutAllergen` |
| Rule / schema knowledge (T-Box) | RC1 `PeanutAllergen subClassOf NutAllergen` ; RC2 `NutAllergen subClassOf (triggers hasValue NutAllergy)` ; RC5 `hasIngredient o containsAllergen -> containsAllergen` ; R1 `containsAllergen(f,a) ^ triggers(a,c) -> unsafeFor(f,c)` |
| Inferred facts | `alg:peanut nr:triggers nr:NutAllergy` ; `dish:chicken_satay nr:containsAllergen alg:peanut` ; `dish:chicken_satay nr:unsafeFor nr:NutAllergy` |
Same result for Almond Cookies (Almonds -> Almond, a TreeNutAllergen) and Pecan Pie (Pecans).

## Example 2 - High-sodium rule (query: `INF2_high_sodium_rule.rq`)
| Step | Content |
|---|---|
| Explicit fact | `food:salt_table nr:sodiumPer100g 38758.00` (USDA, D3) ; `food:cheese_cheddar nr:sodiumPer100g 621.00` |
| Rule | R3 `sodiumPer100g(f,n) ^ n > 600 -> HighSodiumFood(f) ^ unsafeFor(f, Hypertension)` (threshold 600 mg = `rule:hypertension_sodium_avoid`, source WHO) |
| Inferred facts | `food:salt_table a nr:HighSodiumFood` ; `food:salt_table nr:unsafeFor nr:Hypertension` (same for Cheddar: 621 > 600) |

## Example 3 - Low-sugar classification (query: `INF3_low_sugar_rule.rq`)
| Step | Content |
|---|---|
| Explicit fact | `food:broccoli_raw nr:sugarPer100g 1.70` |
| Rule | R4 `sugarPer100g(f,s) ^ s <= 5.0 -> LowSugarFood(f)` |
| Inferred fact | `food:broccoli_raw a nr:LowSugarFood` (also Brown rice, cooked: 0.35 g; Cheddar: 0.52 g) |

Bonus (R5, dishes): a dish is unsafe for T2D / hypertension if any ingredient is, e.g. dishes containing `Salt, Table` become `unsafeFor nr:Hypertension` (see CQ6, CQ8).
