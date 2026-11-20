# NutriReason-KG
Knowledge-grounded advisory system for health-constrained dietary planning (AI-3001 KRR, team krr-08-nutrireason).

Iteration 1 = ontology + RDF knowledge graph + SPARQL + symbolic rules. Iteration 2 = link prediction (PyKEEN), a KG-grounded LLM app and an LLM-only vs KG-grounded evaluation.

## Repository layout
| Folder | Content |
|---|---|
| `Dataset/` | Source CSVs D1-D4 |
| `Ontology/` | `nutrireason_tbox.ttl` (T-Box), `rules_graphdb.ru` (SPARQL rules R1-R5, RC2, RC5) |
| `RDF_Knowledge_Graph/` | `build_kg.py`, `abox.ttl` (explicit A-Box), `inferred.ttl` (rule-derived triples only) |
| `SPARQL_Queries/`, `Results/`, `Visualization/`, `Report/` | Iteration 1 queries, outputs, screenshots, docs |
| `reasoning/` | **Option A link prediction**: `materialize.py`, `link_prediction.py`, `results/` (metrics + predictions) |
| `retrieval/` | **KG retrieval layer** `retriever.py`: entity linking, SPARQL templates, explicit/inferred tags, insufficient-evidence flag |
| `app/` | `llm.py` (prompts + Groq client), `streamlit_app.py` (UI) |
| `evaluation/` | `run_eval.py` (10 CQ, LLM-only vs grounded), `unseen_check.py`, `results/` |

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env        # then put your Groq API key in .env (never commit it)
```
`.env` is git-ignored. `.env.example` holds the sample configuration (no key). Default model: `openai/gpt-oss-120b` on Groq, temperature 0.

## Run
```bash
python RDF_Knowledge_Graph/build_kg.py --data-dir Dataset --out RDF_Knowledge_Graph/abox.ttl --tbox Ontology/nutrireason_tbox.ttl   # rebuild A-Box (optional)
python reasoning/materialize.py            # run rules -> RDF_Knowledge_Graph/inferred.ttl (7,673 inferred triples)
python run_all_queries.py                  # all SPARQL queries offline (rdflib), CSVs in Results/
python reasoning/link_prediction.py        # TransE / RotatE, writes reasoning/results/
python retrieval/retriever.py "Why is Almond Cookies unsafe?"   # prints the retrieval JSON
streamlit run app/streamlit_app.py         # the app
python evaluation/run_eval.py              # 10-CQ comparison -> evaluation/results/
python evaluation/unseen_check.py          # extra unseen questions
```
GraphDB: load `Ontology/nutrireason_tbox.ttl` + `RDF_Knowledge_Graph/abox.ttl`, then run `Ontology/rules_graphdb.ru` (as in Iteration 1). The Python retriever reproduces the same explicit/inferred split with rdflib.

## Provenance labels
Every fact is `explicit` (stored in abox/tbox), `inferred` (derived by schema/rules, in `inferred.ttl`), and LLM output is *generated text*. Link-prediction output (`reasoning/results/predictions_*.csv`) is labelled **PREDICTION** and is never loaded into the retrieval graph.
