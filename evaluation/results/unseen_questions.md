# Unseen-question check (model openai/gpt-oss-120b)

## Is Chicken Satay safe for someone with a nut allergy?
- type: `dish_profile`, sufficient: **True**, entities: ['Nut allergy', 'Chicken Satay'], facts: 15
- reason: Relevant facts retrieved.

**Grounded answer:** No. Chicken Satay contains peanut, which triggers a nut allergy, so it is unsafe for someone with a nut allergy【F12】【F15】.

## Which foods are safe for lactose intolerance and also low in sugar?
- type: `safe_for`, sufficient: **True**, entities: ['Lactose intolerance', 'Sugar'], facts: 47
- reason: 565 foods that the graph classifies (they have a food group) have NO unsafeFor link to Lactose intolerance; 12 shown. 'Safe' = absence of an unsafeFor fact (open-world caveat).

**Grounded answer:** All of the foods shown in the graph are safe for lactose-intolerance (no unsafeFor link is recorded, so safety is inferred) and each has ≤ 5 g sugar per 100 g, meeting the “low-sugar” threshold used for Type 2-diabetes rules.

- Almonds – 3.89 g sugar [F2]  
- Almonds, Blanched – 4.63 g [F5]  
- Almonds, Dry Rstd, W/Salt – 4.93 g [F8]  
- Almonds, Dry Rstd, Wo/Salt – 4.93 g [F11]  
- Almonds, Oil Rstd, W/Salt – 4.55 g [F14]  
- Almonds, Oil Rstd, Wo/Salt – 4.55 g [F17]  
- Apricots, Cnd, H2O Pk, W/Skin, Sol&Liquids – 4.79 g [F20]  
- Artichokes (Globe/ French), cooked, boiled, drained, W/Salt – 0.99 g [F23]  
- Artichokes (Globe/ French), cooked, boiled, drained, Wo/Salt – 0.99 g [F26]  
- Artichokes (Globe/ French), frozen, cooked, boiled, drained, W/Salt – 0.84 g [F29]  
- Artichokes (Globe/ French), frozen, cooked, boiled, drained, Wo/Salt – 0.84 g [F32]  
- Artichokes (Globe/ French), raw – 0.99 g [F35]  

These 12 items are both lactose-intolerance-safe (inferred) and low in sugar.

## Is Kheer a problem for a person with lactose intolerance?
- type: `dish_profile`, sufficient: **True**, entities: ['Lactose intolerance', 'Kheer'], facts: 16
- reason: Relevant facts retrieved.

**Grounded answer:** Yes. Kheer contains dairy, which makes it unsafe for someone with lactose intolerance [F9][F12 (inferred)].

## Which foods have sugar above the diabetes limit?
- type: `above_limit`, sufficient: **True**, entities: ['Type 2 diabetes', 'Sugar'], facts: 38
- reason: 669 foods have sugar above the 22.5 g per 100 g limit for Type 2 diabetes; the 15 highest are shown with exact values.

**Grounded answer:** All of the foods shown have sugar > 22.5 g / 100 g, so they exceed the diabetes “avoid” limit:

- Sugars, Granulated [F1]  
- Sugar, Turbinado [F3]  
- Sugars, Powdered [F5]  
- Whiskey Sour Mix, Pdr [F7]  
- Lemonade-Flavor Drk, Pdr [F9]  
- Sugars, Brown [F11]  
- Sugar [F13]  
- Strawberry-Flavor Bev Mix, Pdr [F15]  
- Tea, Inst, Swtnd W/Sugar, Lemn-Flav, Wo/ Vit C, Pdr, Decaf [F17]  
- Tea, Inst, Swtnd W/Sugar, Lemon-Flavored, Wo/ Vit C, Pdr [F19]  
- Lemonade, Powder [F21]  
- Candies, Hard, Dietetic Or Lo Cal (Sorbitol) [F23]  
- Puddings, Vanilla, Dry Mix, Inst [F25]  
- Sweeteners, Tabletop, Fructose, Dry, Pdr [F27]  
- Orange-Flavor Drk, Brkfst Type, Pdr [F29]  

Each of these foods is marked “unsafeFor Type 2 diabetes” (inferred) and far exceeds the 22.5 g/100 g threshold defined by the American Diabetes Association.

## Is Salt, Table high in sodium?
- type: `food_profile`, sufficient: **True**, entities: ['Salt, Table', 'Sodium'], facts: 8
- reason: Relevant facts retrieved.

**Grounded answer:** Yes. Salt, Table is classified as a high-sodium food [F5] (inferred) and contains 38 758 mg of sodium per 100 g [F2] (explicit).

## What is the capital of France?
- type: `none`, sufficient: **False**, entities: [], facts: 0
- reason: No entity from the graph was recognised in the question.

**Grounded answer:** Insufficient evidence in the knowledge graph to answer this question. The graph does not contain any entities or facts about France or its capital.

## Can I eat dragon fruit curry if I have a nut allergy?
- type: `unknown_item`, sufficient: **False**, entities: ['Nut allergy', 'Fruit'], facts: 0
- reason: The item named in the question is not in the knowledge graph (unmatched words: 'dragon', 'curry'). Only Fruit (FoodType) matched, which is not the item asked about.

**Grounded answer:** Insufficient evidence in the knowledge graph to answer this question. The specific dish “dragon fruit curry” is not represented in the knowledge graph.

## Which dishes contain wheat gluten?
- type: `allergen_dishes`, sufficient: **True**, entities: ['Wheat / Gluten'], facts: 17
- reason: 59 dishes contain Wheat / Gluten (own or via an ingredient); up to 12 shown.

**Grounded answer:** The dishes shown to contain wheat / gluten are:

- Almond Cookies [F1][F2]  
- Aloo Paratha [F3][F4]  
- Baked Ziti [F5][F6]  
- Banana Bread [F7][F2]  
- Berry Cobbler [F8][F2]  
- Blueberry Muffins [F9][F2]  
- Blueberry Pancakes [F10][F2]  
- Butter Naan [F11][F2]  
- Caesar Pasta Salad [F12][F6]  
- Chicken Noodle Casserole [F13][F14]  
- Chicken Parmesan [F15][F16]  
- Chocolate Cake [F17][F2]  

(These are the up-to-12 dishes displayed; the full set includes 59 dishes.)

## Is unicorn stew ok for hypertension?
- type: `unknown_item`, sufficient: **False**, entities: ['Hypertension'], facts: 0
- reason: The item named in the question is not in the knowledge graph (unmatched words: 'unicorn', 'stew').

**Grounded answer:** Insufficient evidence in the knowledge graph to answer this question. The item “unicorn stew” is not present in the knowledge graph.
