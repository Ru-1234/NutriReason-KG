# Unseen-question check (model openai/gpt-oss-120b)

## Is Chicken Satay safe for someone with a nut allergy?
- type: `dish_profile`, sufficient: **True**, entities: ['Nut allergy', 'Chicken Satay'], facts: 15
- reason: Relevant facts retrieved.

**Grounded answer:** No. Chicken Satay contains peanut, which triggers a nut allergy, so it is unsafe for someone with a nut allergy【F12】【F15】.

## Which foods are safe for lactose intolerance and also low in sugar?
- type: `safe_for`, sufficient: **True**, entities: ['Lactose intolerance', 'Sugar'], facts: 47
- reason: 565 foods that the graph classifies (they have a food group) have NO unsafeFor link to Lactose intolerance; 12 shown. 'Safe' = absence of an unsafeFor fact (open-world caveat).

**Grounded answer:** All of the foods shown in the graph have **no unsafeFor link to Lactose intolerance** (so safety is inferred) and their sugar content is ≤ 5 g / 100 g, meeting the “low-sugar” rule (threshold 5.0 g)【F37-F39】【F44-F47】.

**Low-sugar, lactose-intolerance-safe foods**

- **Almonds** – 3.89 g/100 g【F2】  
- **Almonds, blanched** – 4.63 g/100 g【F5】  
- **Almonds, dry roasted, with salt** – 4.93 g/100 g【F8】  
- **Almonds, dry roasted, without salt** – 4.93 g/100 g【F11】  
- **Almonds, oil roasted, with salt** – 4.55 g/100 g【F14】  
- **Almonds, oil roasted, without salt** – 4.55 g/100 g【F17】  
- **Apricots, canned (water pack, with skin)** – 4.79 g/100 g【F20】  
- **Artichokes (cooked, boiled, drained, with salt)** – 0.99 g/100 g【F23】  
- **Artichokes (cooked, boiled, drained, without salt)** – 0.99 g/100 g【F26】  
- **Artichokes (frozen, cooked, boiled, drained, with salt)** – 0.84 g/100 g【F29】  
- **Artichokes (frozen, cooked, boiled, drained, without salt)** – 0.84 g/100 g【F32】  
- **Artichokes (raw)** – 0.99 g/100 g【F35】

These items are therefore both safe for lactose-intolerant individuals (inferred) and low in sugar (explicit).

## Is Kheer a problem for a person with lactose intolerance?
- type: `dish_profile`, sufficient: **True**, entities: ['Lactose intolerance', 'Kheer'], facts: 18
- reason: Relevant facts retrieved.

**Grounded answer:** Yes. Kheer is unsafe for people with lactose intolerance [ F14 ].

## Which foods have sugar above the diabetes limit?
- type: `food_profile`, sufficient: **True**, entities: ['Type 2 diabetes', 'Sugar'], facts: 11
- reason: Relevant facts retrieved.

**Grounded answer:** Sugar exceeds the diabetes limit (95.74 g/100 g > 22.50 g/100 g) and is therefore unsafe for people with Type 2 diabetes【F1】【F10】【F6】.

## Is Salt, Table high in sodium?
- type: `food_profile`, sufficient: **True**, entities: ['Salt, Table', 'Sodium'], facts: 8
- reason: Relevant facts retrieved.

**Grounded answer:** Yes. Salt, Table is classified as a high-sodium food [F6] (inferred) and contains 38 758 mg of sodium per 100 g [F2].

## What is the capital of France?
- type: `none`, sufficient: **False**, entities: [], facts: 0
- reason: No entity from the graph was recognised in the question.

**Grounded answer:** Insufficient evidence in the knowledge graph to answer this question. The graph contains no recognized entities or facts about France or its capital.

## Can I eat dragon fruit curry if I have a nut allergy?
- type: `condition_unsafe`, sufficient: **True**, entities: ['Nut allergy', 'Fruit'], facts: 37
- reason: 9 dishes are unsafe for Nut allergy via an allergen-carrying ingredient (showing up to 12).

**Grounded answer:** Insufficient evidence in the knowledge graph to answer this question. (Missing information about the ingredients or allergens in dragon fruit curry.)

## Which dishes contain wheat gluten?
- type: `allergen_dishes`, sufficient: **True**, entities: ['Wheat / Gluten'], facts: 17
- reason: 59 dishes contain Wheat / Gluten (own or via an ingredient); up to 12 shown.

**Grounded answer:** The following dishes are shown to contain wheat / gluten:

- Almond Cookies → Flour → Wheat / Gluten【F1】【F2】  
- Aloo Paratha → Wheat flour → Wheat / Gluten【F3】【F4】  
- Baked Ziti → Pasta → Wheat / Gluten【F5】【F6】  
- Banana Bread → Flour → Wheat / Gluten【F7】【F2】  
- Berry Cobbler → Flour → Wheat / Gluten【F8】【F2】  
- Blueberry Muffins → Flour → Wheat / Gluten【F9】【F2】  
- Blueberry Pancakes → Flour → Wheat / Gluten【F10】【F2】  
- Butter Naan → Flour → Wheat / Gluten【F11】【F2】  
- Caesar Pasta Salad → Pasta → Wheat / Gluten【F12】【F6】  
- Chicken Noodle Casserole → Noodles → Wheat / Gluten【F13】【F14】  
- Chicken Parmesan → Bread crumbs, Parmesan cheese → Wheat / Gluten【F15】【F16】  
- Chocolate Cake → Flour → Wheat / Gluten【F17】【F2】
