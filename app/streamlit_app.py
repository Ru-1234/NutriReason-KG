"""NutriReason UI.  Run from repo root:  streamlit run app/streamlit_app.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
from retrieval.retriever import KGRetriever
from app import llm

st.set_page_config(page_title="NutriReason-KG", layout="wide")


@st.cache_resource(show_spinner="Loading knowledge graph...")
def get_kg():
    return KGRetriever()


kg = get_kg()
st.title("NutriReason-KG: knowledge-grounded dietary advisor")
st.caption(f"Pipeline: question -> KG retrieval (SPARQL) -> context -> LLM ({llm.MODEL}, T={llm.TEMPERATURE}) -> grounded answer + evidence")
examples = ["Which dishes contain a nut allergen?", "Why is Almond Cookies unsafe, and for which conditions?",
            "Which foods should someone with hypertension avoid?", "Which guideline supports the rule for type 2 diabetes?",
            "Is chocolate syrup ok for type 2 diabetes?", "What is the capital of France?"]
c1, c2 = st.columns([3, 1])
qp = st.query_params
q = c1.text_input("Ask a dietary question", value=qp.get("q", examples[1]))
ex = c2.selectbox("Examples", [""] + examples)
if ex:
    q = ex
compare = st.checkbox("Also show the plain LLM answer (no KG) for comparison", value=qp.get("compare") == "1")
if (st.button("Ask", type="primary") or qp.get("run") == "1") and q:
    r = kg.retrieve(q)
    left, right = st.columns(2)
    with left:
        st.subheader("1. Retrieved from the graph")
        st.write("**Entities linked:**", ", ".join(f"{e['label']} ({e['kind']})" for e in r["entities"]) or "none")
        st.write(f"**Type:** {r['type']}  |  **Sufficient evidence:** {'yes' if r['sufficient'] else 'NO'}")
        st.caption(r["reason"])
        if r["paths"]:
            st.markdown("**Reasoning paths** (exp = explicit, inf = inferred)")
            for p in r["paths"][:12]:
                st.code(p["text"], language=None, wrap_lines=True)
        if r["facts"]:
            st.markdown("**Facts**")
            st.dataframe([{"id": f["id"], "subject": f["subject"], "predicate": f["predicate"], "object": f["object"],
                           "tag": f["tag"]} for f in r["facts"]], use_container_width=True, hide_index=True)
        with st.expander("SPARQL executed"):
            for s in r["queries"]:
                st.code(s, language="sparql")
    with right:
        st.subheader("2. Grounded answer (generated text)")
        with st.spinner("Calling LLM..."):
            ans = llm.answer_grounded(q, r)
        (st.info if r["sufficient"] else st.warning)(ans)
        st.caption("Generated text. Facts it cites are labelled explicit / inferred in the table. Link predictions are never used as facts.")
        if compare:
            st.subheader("Plain LLM (no KG)")
            st.error(llm.answer_llm_only(q))
