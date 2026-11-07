# SPARQL equivalents of the SWRL rules, for GraphDB (which does not run SWRL).
# Run once after loading tbox + abox. Derived triples go to the default graph;
# use a named graph (INSERT INTO) if you want to keep them separate.

PREFIX nr:  <http://example.org/nutrireason#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

# ---- R1: allergen -> condition (uses explicit AND chain-inherited allergens) ----
# Dishes inherit ingredient allergens via the path hasIngredient/containsAllergen,
# so we materialise that first (RC5), then R1.
INSERT { ?dish nr:containsAllergen ?a }
WHERE  { ?dish nr:hasIngredient ?ing . ?ing nr:containsAllergen ?a . } ;

INSERT { ?f nr:unsafeFor ?c }
WHERE  { ?f nr:containsAllergen ?a . ?a nr:triggers ?c . } ;

# ---- RC2: allergen class -> condition (hasValue restriction, materialised) ----
INSERT { ?a nr:triggers nr:NutAllergy }
WHERE  { ?a a ?cls . ?cls rdfs:subClassOf* nr:NutAllergen . } ;

INSERT { ?a nr:triggers nr:LactoseIntolerance }
WHERE  { ?a a ?cls . ?cls rdfs:subClassOf* nr:DairyAllergen . } ;

# ---- R2: high sugar ----
INSERT { ?f a nr:HighSugarFood ; nr:unsafeFor nr:Type2Diabetes }
WHERE  { ?f nr:sugarPer100g ?s . FILTER(?s > 22.5) } ;

# ---- R3: high sodium ----
INSERT { ?f a nr:HighSodiumFood ; nr:unsafeFor nr:Hypertension }
WHERE  { ?f nr:sodiumPer100g ?n . FILTER(?n > 600) } ;

# ---- R4: low sugar ----
INSERT { ?f a nr:LowSugarFood }
WHERE  { ?f nr:sugarPer100g ?s . FILTER(?s <= 5) } ;
