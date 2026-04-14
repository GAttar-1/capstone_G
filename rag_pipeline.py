# ---------- rag_pipeline.py ----------
import os
import re
import random
from openai import OpenAI
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()

import streamlit as st

# Initialize clients with caching for performance boost
@st.cache_resource
def get_pinecone_index():
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    return pc.Index("officialreportingxpress")

@st.cache_resource
def get_openai_client():
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

openai_client = get_openai_client()
index = get_pinecone_index()

# Set this to False to instantly revert to raw, fast searching without LLM intervention
USE_HYDE = True

APPROVED_ANALYTICS_VOCAB = [
    "lapse",
    "recaptured",
    "New donors",
    "retention rate",
    "retained",
    "lapse rate",
    "increasing gift amounts",
    "decreasing gift amounts",
    "seasonal and timing patterns",
    "lifetime value",
    "last fiscal year",
    "current fiscal year",
    "concentration risk",
    "new donor conversion",
    "top segment",
    "middle segment",
    "bottom segment",
    "waterfall analysis",
    "tenure",
    "first-time",
    "QX147", # Recently Lapsed 18 Month
]

ANSWER_LEAK_PATTERNS = [
    r"\byou should\b",
    r"\bwe recommend\b",
    r"\bi recommend\b",
    r"\bthe best strategy\b",
    r"\bnext step\b",
    r"\baction item\b",
    r"\byour .*?(rate|value|revenue|performance) is\b",
]


def flag_chunk_in_pinecone(chunk_id: str):
    """
    Marks a specific Pinecone vector as flagged for low quality.
    Called when user clicks 👎 on an answer. The chunk is not deleted
    immediately — it is tagged so future retrieval can filter it out
    or it can be batch-deleted during maintenance.
    """
    try:
        index.update(
            id=chunk_id,
            set_metadata={"flagged": True},
            namespace="__default__"
        )
        return True
    except Exception as e:
        print(f"[Pinecone flag error] {chunk_id}: {e}")
        return False

def _normalize_query_text(text: str) -> str:
    """Normalizes model output to a single clean line for embedding."""
    cleaned = (text or "").strip().strip('"').strip("'")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _contains_answer_like_content(text: str) -> bool:
    lowered = (text or "").lower()
    return any(re.search(pattern, lowered) for pattern in ANSWER_LEAK_PATTERNS)


def _build_vocab_terms(question: str):
    """Maps user phrasing to approved retrieval vocabulary terms."""
    q = (question or "").lower()
    terms = []

    if any(token in q for token in ["lapse", "lapsed", "attrition"]):
        terms.extend(["lapse", "recaptured"])
    if any(token in q for token in ["retention", "keep", "churn"]):
        terms.append("retention rate")
    if any(token in q for token in ["ltv", "lifetime", "value"]):
        terms.append("lifetime value")
    if any(token in q for token in ["top", "major", "segment", "tier"]):
        terms.append("top segment")
    if any(token in q for token in ["funnel", "drop", "transition", "waterfall"]):
        terms.append("waterfall analysis")
    if any(token in q for token in ["tenure", "years", "new vs", "new", "aging"]):
        terms.append("tenure")
    if any(token in q for token in ["fiscal", "fy", "year over year", "yoy"]):
        terms.append("fiscal year metrics")

    # Preserve order while de-duplicating.
    seen = set()
    deduped = []
    for term in terms:
        if term not in seen:
            deduped.append(term)
            seen.add(term)
    return deduped


def _safe_reframed_query(model_text: str, original_question: str) -> str:
    """Ensures transformed query is reframed-only and never answer-like."""
    candidate = _normalize_query_text(model_text)
    if not candidate:
        return original_question

    if _contains_answer_like_content(candidate):
        return original_question

    # Keep retrieval-focused terms compactly appended.
    vocab_terms = _build_vocab_terms(original_question)
    if vocab_terms:
        missing = [t for t in vocab_terms if t.lower() not in candidate.lower()]
        if missing:
            candidate = f"{candidate} | terms: {', '.join(missing[:3])}"

    return candidate

@st.cache_data(show_spinner=False)
def transform_query(question):
    """
    Reframes the user question into a retrieval query without answering it.
    """
    if not USE_HYDE:
        return question

    prompt = f"""
Rewrite the user question as a search query for a fundraising RAG system.

Rules (CRITICAL):
- Strictly Reframe. Do NOT answer the question.
- Use only approved technical vocabulary: {', '.join(APPROVED_ANALYTICS_VOCAB)}.
- If the user mentions "lost" or "lapsed" donors, always include "QX147" or "Recently Lapsed 18 Month".
- Simplify the intent. Remove fluff, greetings, or filler words.
- Output EXACTLY one line of plain keywords/phrases.
- BANNED: advice, recommendations, pronouns like 'we' or 'you'.

User question: {question}
"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a retrieval query rewriter. "
                        "You only rewrite the user query for semantic search. "
                        "Never answer the question."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        rewritten = response.choices[0].message.content
        return _safe_reframed_query(rewritten, question)
    except Exception:
        # Safe fallback: never block retrieval if rewrite fails.
        return question

def retrieve_chunks(question):
    """Embeds user question, searches Pinecone, and forces deep page retrieval for source diversity."""
    
    # --- CONFIDENCE UPGRADE: HYDE TRANSFORMATION ---
    search_query = transform_query(question)
    
    embedding = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=search_query
    )

    query_vector = embedding.data[0].embedding

    # Fetch a massive net of 60 chunks to ensure we catch deep pages
    results = index.query(
        vector=query_vector,
        top_k=60, 
        include_metadata=True,
        namespace="__default__"
    )

    source_groups = {}

    # Group the matching chunks by their base document
    for match in results["matches"]:
        metadata = match["metadata"]
        text = metadata.get("text", "")
        
        full_source_id = metadata.get("citation_id") or metadata.get("source_file") or "Unknown Source"
        base_source = re.sub(r'(?i),?\s*page\s*\d+.*', '', full_source_id).strip()

        if text:
            if base_source not in source_groups:
                source_groups[base_source] = []
            source_groups[base_source].append({
                "id": full_source_id,
                "text": text,
                "score": match["score"] * 100
            })

    qx_docs = []
    other_docs = []

    for base_source, chunks in source_groups.items():
        if "QX" in base_source.upper():
            qx_docs.append(chunks)
        else:
            other_docs.append(chunks)

    contexts = []
    
    # Pick 2-3 unique QX documents
    qx_selection = qx_docs[:3]
    for chunks in qx_selection:
        chosen_chunk = random.choice(chunks[:3])
        contexts.append(chosen_chunk)
        
    # Pick 2-3 unique Other documents
    other_selection = other_docs[:(6 - len(contexts))] if len(contexts) < 3 else other_docs[:3]
    for chunks in other_selection:
        chosen_chunk = random.choice(chunks[:3])
        contexts.append(chosen_chunk)

    return contexts, search_query

def ask_ai(question, require_logic=True):
    """Passes context to the LLM. Dynamically requests logic based on the UI toggle."""
    
    contexts, search_query = retrieve_chunks(question)

    formatted_contexts = []
    for ctx in contexts:
        formatted_contexts.append(f"[Source ID: {ctx['id']}]\n{ctx['text']}")
        
    context_text = "\n\n".join(formatted_contexts)

    logic_prompt = ""
    if require_logic:
        logic_prompt = """
3. LOGIC PARSING: At the very end of your response, you MUST include a 'Reasoning Path' labeled exactly as "LOGIC:". 
CRITICAL: Do not use bullet points or markdown bolding. You must use exactly these three uppercase labels:
DIAGNOSIS: [State the core donor behavior or challenge you identified]
EVIDENCE: [List the 4 to 5 distinct sources you combined]
STRATEGY: [State how this logically leads to your recommendation]
"""

    prompt = f"""
You are Rex, the intelligent fundraising strategist and RAG (Retrieval-Augmented Generation) assistant for Reporting Xpress. 
Your primary purpose is to help nonprofit professionals identify WHICH analytics, metrics, or dashboard reports they should look at to solve their current challenge.

## Your Identity & Restrictions (CRITICAL)
- You DO NOT have access to the user's actual, live database. You are completely blind to their specific numbers.
- You must NEVER attempt to calculate, project, or invent hard data (e.g., never say "your retention rate is 45%" or "your revenue will grow").
- Instead, you must act as a navigator. Tell the user exactly *what data they should be looking at* within their organization, which analytics will uncover the answer, and *why*.

## Core Rules & Grounding
- STRICT CONTEXT: You must base your strategic advice strictly on the Context provided below.
- FOCUS ON ANALYTICS: Recommend specific types of reviews (e.g., "Year-Over-Year Variance", "Donor Upgrade Pipeline", or "Retention Hub") based on industry research.

## Required Mechanics (CRITICAL)
1. THE RULE OF FIVE (MANDATORY): You are provided with diverse documents. You MUST extract facts or strategies from at least FOUR TO FIVE DISTINCT Source IDs. 
2. DIVERSE PERSPECTIVES: You must cite BOTH 'QX' internal reports AND external research / industry context.
3. INLINE CITATIONS: You must explicitly cite every claim using the exact Source ID immediately after the relevant sentence, like this: "Data shows an increase in retention [Annual Report 2025, Page 14]."
{logic_prompt}

Context:
{context_text}

User Question:
{question}
"""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.0, 
        messages=[
            {
                "role": "system", 
                "content": (
                    "You are Rex, the intelligent fundraising strategist. "
                    "CORE SCOPE: The CI Hub ONLY contains analytics based on RFM metrics "
                    "(Recency, Frequency, Monetary Value). It DOES NOT contain engagement "
                    "(emails, events) or enrichment (wealth) data. "
                    "If the user asks for engagement or enrichment info, recommend the closest "
                    "RFM analytic and explicitly state: 'Blend these RFM based analytics with "
                    "engagement analytics for a better picture.' "
                    "STRICT GROUNDING: You MUST cite at least 4 to 5 UNIQUE sources. "
                    "Do NOT invent analytic names; only use names found in the Context."
                )
            },
            {"role": "user", "content": prompt}
        ]
    )

    raw_answer = response.choices[0].message.content
    
    # --- VERIFICATION PASS: Eliminiate Hallucinations ---
    verified_answer = verify_response_pass(question, raw_answer, contexts)
    final_answer = verified_answer
    
    logic_html = "<div class='logic-step' tabindex='0'><div class='logic-detail'>Transparency Mode disabled.</div></div>"
    
    if require_logic and "LOGIC:" in raw_answer:
        parts = re.split(r'[*#]*\s*LOGIC:\s*[*#]*', raw_answer, maxsplit=1)
        
        if len(parts) > 1:
            final_answer = parts[0].strip()
            raw_logic = parts[1].strip()
            
            diag_match = re.search(r'DIAGNOSIS:\s*(.*?)(?=EVIDENCE:|$)', raw_logic, re.DOTALL | re.IGNORECASE)
            evid_match = re.search(r'EVIDENCE:\s*(.*?)(?=STRATEGY:|$)', raw_logic, re.DOTALL | re.IGNORECASE)
            strat_match = re.search(r'STRATEGY:\s*(.*?)$', raw_logic, re.DOTALL | re.IGNORECASE)
            
            diag_text = diag_match.group(1).strip().replace("**", "").replace("-", "") if diag_match else "Identified core challenge."
            evid_text = evid_match.group(1).strip().replace("**", "").replace("-", "") if evid_match else "Synthesized 4-5 distinct sources."
            strat_text = strat_match.group(1).strip().replace("**", "").replace("-", "") if strat_match else "Formulated recommendation."
            
            logic_html = f"""
            <div class="logic-step" tabindex="0" aria-label="Diagnosis: {diag_text}">
                <div class="logic-label label-diag">🔍 DIAGNOSIS</div>
                <div class="logic-detail">{diag_text}</div>
            </div>
            <div class="logic-step" tabindex="0" aria-label="Evidence: {evid_text}">
                <div class="logic-label label-evid">📊 EVIDENCE</div>
                <div class="logic-detail">{evid_text}</div>
            </div>
            <div class="logic-step" style="border-left-color: transparent;" tabindex="0" aria-label="Strategy: {strat_text}">
                <div class="logic-label label-strat">🎯 STRATEGY</div>
                <div class="logic-detail">{strat_text}</div>
            </div>
            """
    
    avg_confidence = sum(c['score'] for c in contexts) / len(contexts) if contexts else 100
    
    return {
        "answer": final_answer,
        "logic": logic_html, 
        "sources": contexts,
        "avg_confidence": avg_confidence,
        "search_query": search_query
    }

def verify_response_pass(question, assistant_answer, contexts):
    """
    A second pass to verify that every recommended analytic name is grounded 
    in the provided Source IDs. Removes 'creative' hallucinations.
    """
    formatted_contexts = []
    for ctx in contexts:
        formatted_contexts.append(f"[Source ID: {ctx['id']}]\n{ctx['text']}")
    context_text = "\n\n".join(formatted_contexts)

    prompt = f"""
    You are a meticulous Verification Assistant for Reporting Xpress. 
    I will provide you with a Strategy Recommendation generated by another AI.
    Your task is to VERIFY that every specific analytic, report, or dashboard mentioned 
    exists within the provided Context below.
    
    CRITICAL: 
    - If you find a hallucinated or 'descriptive' analytic name (e.g., 'Donor Loss Predictor') 
      that does not appear in the Source IDs, replace it with the most relevant REAL analytic name 
      found in the sources (e.g., 'Lapsed Donor Review').
    - Maintain the exact tone and citations of the original answer.
    - If the answer includes 'Blend these RFM based analytics with engagement analytics...', 
      keep that phrase intact.
    - Your output must ONLY be the verified text of the final recommendation. No commentary.

    Original Query: {question}
    Original Recommendation: {assistant_answer}
    
    Context:
    {context_text}
    """

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.0,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def ask_ai_stream(question, require_logic=True, history=None):
    """
    Streaming version of ask_ai. Performs retrieval up front, then yields
    raw text tokens from the LLM in real-time.
    
    history: list of dicts [{"role": "user"|"assistant", "content": str}, ...]
             The last 3-5 turns from the session, used for short-term memory.
    """
    contexts, search_query = retrieve_chunks(question)

    formatted_contexts = []
    for ctx in contexts:
        formatted_contexts.append(f"[Source ID: {ctx['id']}]\n{ctx['text']}")
    context_text = "\n\n".join(formatted_contexts)

    logic_prompt = ""
    if require_logic:
        logic_prompt = """
3. LOGIC PARSING: At the very end of your response, you MUST include a 'Reasoning Path' labeled exactly as "LOGIC:". 
CRITICAL: Do not use bullet points or markdown bolding. You must use exactly these three uppercase labels:
DIAGNOSIS: [State the core donor behavior or challenge you identified]
EVIDENCE: [List the 4 to 5 distinct sources you combined]
STRATEGY: [State how this logically leads to your recommendation]
"""

    prompt = f"""
You are Rex, the intelligent fundraising strategist and RAG (Retrieval-Augmented Generation) assistant for Reporting Xpress. 
Your primary purpose is to help nonprofit professionals identify WHICH analytics, metrics, or dashboard reports they should look at to solve their current challenge.

## Your Identity & Restrictions (CRITICAL)
- You DO NOT have access to the user's actual, live database. You are completely blind to their specific numbers.
- You must NEVER attempt to calculate, project, or invent hard data (e.g., never say "your retention rate is 45%" or "your revenue will grow").
- Instead, you must act as a navigator. Tell the user exactly *what data they should be looking at* within their organization, which analytics will uncover the answer, and *why*.

## Core Rules & Grounding
- STRICT CONTEXT: You must base your strategic advice strictly on the Context provided below.
- FOCUS ON ANALYTICS: Recommend specific types of reviews (e.g., "Year-Over-Year Variance", "Donor Upgrade Pipeline", or "Retention Hub") based on industry research.

## Required Mechanics (CRITICAL)
1. THE RULE OF FIVE (MANDATORY): You are provided with diverse documents. You MUST extract facts or strategies from at least FOUR TO FIVE DISTINCT Source IDs. 
2. DIVERSE PERSPECTIVES: You must cite BOTH 'QX' internal reports AND external research / industry context.
3. INLINE CITATIONS: You must explicitly cite every claim using the exact Source ID immediately after the relevant sentence, like this: "Data shows an increase in retention [Annual Report 2025, Page 14]."
{logic_prompt}

Context:
{context_text}

User Question:
{question}
"""

    system_msg = (
        "You are Rex, the intelligent fundraising strategist. "
        "CORE SCOPE: The CI Hub ONLY contains analytics based on RFM metrics "
        "(Recency, Frequency, Monetary Value). It DOES NOT contain engagement "
        "(emails, events) or enrichment (wealth) data. "
        "If the user asks for engagement or enrichment info, recommend the closest "
        "RFM analytic and explicitly state: 'Blend these RFM based analytics with "
        "engagement analytics for a better picture.' "
        "STRICT GROUNDING: You MUST cite at least 4 to 5 UNIQUE sources. "
        "Do NOT invent analytic names; only use names found in the Context."
    )

    def build_messages(system_content, history_turns, user_prompt):
        """Builds the OpenAI messages array with optional conversation history."""
        msgs = [{"role": "system", "content": system_content}]
        if history_turns:
            # Strip HTML from assistant messages before sending to the model
            for turn in history_turns:
                clean_content = re.sub(r"<[^>]+>", "", turn.get("content", "")).strip()
                msgs.append({"role": turn["role"], "content": clean_content})
        msgs.append({"role": "user", "content": user_prompt})
        return msgs

    stream = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.0,
        stream=True,
        messages=build_messages(system_msg, history, prompt)
    )

    raw_answer = ""
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            raw_answer += delta
            yield ("token", delta)

    # --- Post-stream: parse logic and build metadata ---
    # --- VERIFICATION PASS: Eliminate Hallucinations ---
    verified_answer = verify_response_pass(question, raw_answer, contexts)
    final_answer = verified_answer
    logic_html = "<div class='logic-step' tabindex='0'><div class='logic-detail'>Transparency Mode disabled.</div></div>"

    if require_logic and "LOGIC:" in raw_answer:
        parts = re.split(r'[*#]*\s*LOGIC:\s*[*#]*', raw_answer, maxsplit=1)
        if len(parts) > 1:
            final_answer = parts[0].strip()
            raw_logic = parts[1].strip()

            diag_match = re.search(r'DIAGNOSIS:\s*(.*?)(?=EVIDENCE:|$)', raw_logic, re.DOTALL | re.IGNORECASE)
            evid_match = re.search(r'EVIDENCE:\s*(.*?)(?=STRATEGY:|$)', raw_logic, re.DOTALL | re.IGNORECASE)
            strat_match = re.search(r'STRATEGY:\s*(.*?)$', raw_logic, re.DOTALL | re.IGNORECASE)

            diag_text = diag_match.group(1).strip().replace("**", "").replace("-", "") if diag_match else "Identified core challenge."
            evid_text = evid_match.group(1).strip().replace("**", "").replace("-", "") if evid_match else "Synthesized 4-5 distinct sources."
            strat_text = strat_match.group(1).strip().replace("**", "").replace("-", "") if strat_match else "Formulated recommendation."

            logic_html = f"""
            <div class="logic-step" tabindex="0" aria-label="Diagnosis: {diag_text}">
                <div class="logic-label label-diag">🔍 DIAGNOSIS</div>
                <div class="logic-detail">{diag_text}</div>
            </div>
            <div class="logic-step" tabindex="0" aria-label="Evidence: {evid_text}">
                <div class="logic-label label-evid">📊 EVIDENCE</div>
                <div class="logic-detail">{evid_text}</div>
            </div>
            <div class="logic-step" style="border-left-color: transparent;" tabindex="0" aria-label="Strategy: {strat_text}">
                <div class="logic-label label-strat">🎯 STRATEGY</div>
                <div class="logic-detail">{strat_text}</div>
            </div>
            """

    avg_confidence = sum(c['score'] for c in contexts) / len(contexts) if contexts else 100

    yield ("meta", {
        "answer": final_answer,
        "logic": logic_html,
        "sources": contexts,
        "avg_confidence": avg_confidence,
        "search_query": search_query
    })