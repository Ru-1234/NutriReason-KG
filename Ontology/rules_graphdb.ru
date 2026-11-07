# SPARQL equivalents of the SWRL rules, for GraphDB (which does not run SWRL).
# Run once after loading tbox + abox. Order matters: triggers -> chain -> unsafeFor.

PREFIX nr:   <http://example.org/nutrireason#>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

# ---- RC2: allergen class -> condition (hasValue restriction, materialised) ----
INSERT { ?a nr:triggers nr:NutAllergy }
WHERE  { ?a a ?cls . ?cls rdfs:subClassOf* nr:NutAllergen . } ;

INSERT { ?a nr:triggers nr:LactoseIntolerance }
WHERE  { ?a a ?cls . ?cls rdfs:subClassOf* nr:DairyAllergen . } ;

# ---- RC5: dishes inherit ingredient allergens ----
INSERT { ?dish nr:containsAllergen ?a }
WHERE  { ?dish nr:hasIngredient ?ing . ?ing nr:containsAllergen ?a . } ;

# ---- R1: allergen -> condition ----
INSERT { ?f nr:unsafeFor ?c }
WHERE  { ?f nr:containsAllergen ?a . ?a nr:triggers ?c . } ;

# ---- R2: high sugar ----
INSERT { ?f a nr:HighSugarFood ; nr:unsafeFor nr:Type2Diabetes }
WHERE  { ?f nr:sugarPer100g ?s . FILTER(?s > 22.5) } ;

# ---- R3: high sodium ----
INSERT { ?f a nr:HighSodiumFood ; nr:unsafeFor nr:Hypertension }
WHERE  { ?f nr:sodiumPer100g ?n . FILTER(?n > 600) } ;

# ---- R4: low sugar ----
INSERT { ?f a nr:LowSugarFood }
WHERE  { ?f nr:sugarPer100g ?s . FILTER(?s <= 5) } ;

# ---- R5: a dish is unsafe for a nutrient condition if any ingredient is (run after R2/R3) ----
INSERT { ?d nr:unsafeFor ?c }
WHERE  { ?d nr:hasIngredient ?i . ?i nr:unsafeFor ?c .
         FILTER (?c IN (nr:Type2Diabetes, nr:Hypertension)) }
