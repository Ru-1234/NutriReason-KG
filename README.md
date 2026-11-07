# NutriReason — Knowledge Graph & Ontology (Iteration 1)

**Team:** krr-08-nutrireason  
**Course:** AI-3001 Knowledge Representation & Reasoning  
**Domain:** Healthcare / Dietary Safety Advisory  

## Overview
This repository contains the ontology schema (T-Box), data transformation pipeline, and generated RDF Knowledge Graph (A-Box) for **NutriReason**, a knowledge-grounded advisory system for health-constrained dietary planning.

## Knowledge Graph Stats
- **Total Triples:** 42,344 (41,948 A-Box triples + 396 T-Box triples)
- **Entities:** 183 foods (D1), 259 dishes (D2), 5,140 nutrient profiles (D3), and 5 core dietary rules (D4).

## Project Structure
- `Ontology/`: Contains `nutrireason_tbox.ttl` (OWL/Turtle ontology defining classes, properties, and constraints).
- `RDF_Knowledge_Graph/`: Contains `build_kg.py` script and the generated `abox.ttl` file.
- `Dataset/`: Source CSV files (`D1` through `D4`).
- `Report/`: Data pipeline documentation (`DATA_PIPELINE.md`).

## How to Run
```bash
pip install pandas rdflib
python RDF_Knowledge_Graph/build_kg.py --data-dir Dataset --out RDF_Knowledge_Graph/abox.ttl --tbox Ontology/nutrireason_tbox.ttl
