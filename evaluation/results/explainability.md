# Explainability examples

Tags: **explicit** = stored in the graph, **inferred** = derived by schema/rules, *generated text* = LLM output.

## Example 1: Is chocolate syrup ok for type 2 diabetes?

**Retrieval:** type `food_profile`, sufficient = True, entities = ['Type 2 diabetes', 'Chocolate Syrup']

**Retrieved facts**

| id | tag | subject | predicate | object |
|---|---|---|---|---|
| F1 | explicit | Chocolate Syrup | nr:sugarPer100g | 49.65 |
| F2 | explicit | Chocolate Syrup | nr:sodiumPer100g | 72.00 |
| F3 | explicit | Chocolate Syrup | nr:caloriesPer100g | 279.00 |
| F4 | inferred | Chocolate Syrup | nr:unsafeFor | Type 2 diabetes |
| F5 | inferred | Chocolate Syrup | rdf:type | High-sugar food |
| F6 | explicit | Type2Diabetes / Sugar / avoid | nr:thresholdValue | 22.50 |
| F7 | explicit | Hypertension / Sodium / avoid | nr:thresholdValue | 600.00 |

**Reasoning paths**


**Generated text (LLM answer):**

> Chocolate syrup is not suitable for someone with type 2 diabetes. It contains 49.65 g of sugar per 100 g (F1), which exceeds the diabetes-related sugar avoidance threshold of 22.5 g per 100 g (F6). Accordingly, the knowledge graph infers that chocolate syrup is unsafe for type 2 diabetes (F4).

## Example 2: Why is Chicken Satay unsafe for a nut allergy?

**Retrieval:** type `dish_profile`, sufficient = True, entities = ['Nut allergy', 'Chicken Satay']

**Retrieved facts**

| id | tag | subject | predicate | object |
|---|---|---|---|---|
| F1 | explicit | Chicken Satay | nr:hasIngredient | Chicken |
| F2 | explicit | Chicken Satay | nr:hasIngredient | Peanut butter |
| F3 | explicit | Chicken Satay | nr:hasIngredient | Soy sauce |
| F4 | explicit | Soy sauce | nr:containsAllergen | Soy / Legume |
| F5 | explicit | Peanut butter | nr:containsAllergen | Dairy |
| F6 | inferred | Dairy | nr:triggers | Lactose intolerance |
| F7 | explicit | Peanut butter | nr:containsAllergen | Peanut |
| F8 | inferred | Peanut | nr:triggers | Nut allergy |
| F9 | explicit | Chicken | nr:containsAllergen | Chicken |
| F10 | inferred | Chicken Satay | nr:containsAllergen | Chicken |
| F11 | inferred | Chicken Satay | nr:containsAllergen | Dairy |
| F12 | inferred | Chicken Satay | nr:containsAllergen | Peanut |
| F13 | inferred | Chicken Satay | nr:containsAllergen | Soy / Legume |
| F14 | inferred | Chicken Satay | nr:unsafeFor | Lactose intolerance |
| F15 | inferred | Chicken Satay | nr:unsafeFor | Nut allergy |

**Reasoning paths**

- `Chicken Satay -[hasIngredient (exp)]-> Soy sauce -[containsAllergen (exp)]-> Soy / Legume`
- `Chicken Satay -[hasIngredient (exp)]-> Peanut butter -[containsAllergen (exp)]-> Dairy -[triggers (inf)]-> Lactose intolerance`
- `Chicken Satay -[hasIngredient (exp)]-> Peanut butter -[containsAllergen (exp)]-> Peanut -[triggers (inf)]-> Nut allergy`
- `Chicken Satay -[hasIngredient (exp)]-> Chicken -[containsAllergen (exp)]-> Chicken`

**Generated text (LLM answer):**

> Chicken Satay contains peanut butter as an ingredient [F2]. Peanut butter contains the peanut allergen [F7], and peanut is known to trigger a nut allergy [F8]. Therefore the dish can provoke a nut-allergy reaction, making it unsafe for people with a nut allergy [F15].

## Example 3: Which guideline supports the rule that makes Bacon Bits, Meatless unsafe for hypertension?

**Retrieval:** type `rule_info`, sufficient = True, entities = ['Hypertension', 'Bacon Bits, Meatless']

**Retrieved facts**

| id | tag | subject | predicate | object |
|---|---|---|---|---|
| F1 | inferred | Bacon Bits, Meatless | nr:unsafeFor | Hypertension |
| F2 | explicit | Hypertension | nr:hasRule | Hypertension / Sodium / avoid |
| F3 | explicit | Hypertension / Sodium / avoid | nr:hasSource | World Health Organization |
| F4 | explicit | Hypertension / Sodium / avoid | nr:thresholdValue | 600.00 |
| F5 | explicit | Hypertension / Sodium / avoid | nr:ruleAction | avoid |

**Reasoning paths**

- `Bacon Bits, Meatless -[unsafeFor (inf)]-> Hypertension -[hasRule (exp)]-> Hypertension / Sodium / avoid -[hasSource (exp)]-> World Health Organization`
- `Hypertension -[hasRule (exp)]-> Hypertension / Sodium / avoid -[hasSource (exp)]-> World Health Organization`

**Generated text (LLM answer):**

> The rule that makes Bacon Bits, Meatless unsafe for hypertension is supported by the **World Health Organization** guideline [ F3 ].
