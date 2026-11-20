"""LLM access (Groq, OpenAI-compatible REST) + the two prompts: LLM-only and KG-grounded."""
import os, time, json, requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _env():
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)


_env()
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
TEMPERATURE = 0.0

SYSTEM_LLM_ONLY = ("You are a dietary-safety assistant. Answer the user's question concisely (max 120 words) "
                   "using your own knowledge.")

SYSTEM_GROUNDED = """You are NutriReason, a dietary-safety assistant that answers ONLY from the retrieved knowledge-graph context.
Rules:
1. Use only the facts and paths in the context. Never add food, nutrient, allergen or guideline information from your own knowledge.
2. Cite the supporting facts by id in square brackets, e.g. [F3][F7], after each claim.
3. Each fact is tagged explicit (stored in the graph) or inferred (derived by schema/rules). Say so when it matters, e.g. "(inferred)".
4. If the context is empty, flagged insufficient, or does not contain what is needed to answer, reply exactly:
   "Insufficient evidence in the knowledge graph to answer this question." and optionally say what is missing. Do not guess.
5. If the context lists only a sample (the reason line says "showing N"), say the list is partial.
6. Be concise (max 150 words)."""


def format_context(r):
    lines = [f"Question type: {r['type']} | sufficient: {r['sufficient']} | note: {r['reason']}", "FACTS:"]
    for f in r["facts"]:
        lines.append(f"[{f['id']}] ({f['tag']}) {f['subject']} | {f['predicate']} | {f['object']}")
    lines.append("REASONING PATHS:")
    for p in r["paths"][:15]:
        lines.append(f"- {p['text']}  (facts: {', '.join(p['fact_ids'])})")
    return "\n".join(lines)


def chat(system, user, retries=5):
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY missing: copy .env.example to .env and fill it in.")
    body = {"model": MODEL, "temperature": TEMPERATURE, "max_tokens": 1500,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    for i in range(retries):
        resp = requests.post("https://api.groq.com/openai/v1/chat/completions", json=body, timeout=90,
                             headers={"Authorization": f"Bearer {key}"})
        if resp.status_code == 429 or resp.status_code >= 500:
            time.sleep(5 * (i + 1)); continue
        resp.raise_for_status()
        txt = (resp.json()["choices"][0]["message"].get("content") or "").strip()
        # the model sometimes emits typographic spaces/hyphens/zero-width chars; normalise them
        return txt.translate({0x202f: " ", 0xa0: " ", 0x200b: None, 0x2011: "-", 0x2010: "-"})
    raise RuntimeError("LLM call failed after retries")


def answer_llm_only(question):
    return chat(SYSTEM_LLM_ONLY, question)


def answer_grounded(question, retrieval):
    user = f"CONTEXT FROM THE KNOWLEDGE GRAPH:\n{format_context(retrieval)}\n\nQUESTION: {question}"
    return chat(SYSTEM_GROUNDED, user)
