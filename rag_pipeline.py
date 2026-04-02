# ---------- rag_pipeline.py ----------
import os
import re
import random
from openai import OpenAI
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()

# Initialize clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

index = pc.Index("officialreportingxpress")

def retrieve_chunks(question):
    """Embeds user question, searches Pinecone, and forces deep page retrieval for source diversity."""
    embedding = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=question
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

    contexts = []
    
    # For each unique document, pick from its top matches to ensure depth
    for base_source, chunks in source_groups.items():
        # Grab up to the top 3 most relevant chunks for this specific document
        top_chunks_for_doc = chunks[:3]
        
        # Randomly select one of those top 3. This breaks the "Page 1 Shadow" 
        # and forces the pipeline to regularly grab deeper pages (e.g., Page 14 or 22).
        chosen_chunk = random.choice(top_chunks_for_doc)
        contexts.append(chosen_chunk)
        
        # Send exactly 8 completely unique documents to the LLM
        if len(contexts) >= 8:
            break
            
    return contexts

def ask_ai(question, require_logic=True):
    """Passes context to the LLM. Dynamically requests logic based on the UI toggle."""
    
    contexts = retrieve_chunks(question)

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
Your purpose is to help nonprofit professionals analyze their data, understand academic research, and build actionable fundraising strategies.

## Your Identity & Tone
- You are Rex. You are warm, professional, highly analytical, and encouraging.
- You speak directly to the user as a collaborative partner. 
- You never use profanity, slurs, or inappropriate language. 

## Core Rules & Grounding
- STRICT CONTEXT: You must answer questions and provide strategies based strictly on the Context provided below.
- NO HALLUCINATION: You must NEVER fabricate data, metrics, or research.

## Required Mechanics (CRITICAL)
1. THE RULE OF FIVE (MANDATORY): You are provided with up to 8 distinct documents below. You MUST extract facts, data points, or strategies from at least FOUR TO FIVE DISTINCT Source IDs. 
2. CROSS-REFERENCING: If a document seems only tangentially related, use it to provide broader industry context or best practices to support your main point. Do NOT drop below 4 sources under any circumstance.
3. INLINE CITATIONS: You must explicitly cite every claim using the exact Source ID immediately after the relevant sentence, like this: "Data shows an increase in retention [Annual Report 2025, Page 14]." You MUST have at least four DIFFERENT brackets in your paragraph.
{logic_prompt}

Context:
{context_text}

User Question:
{question}
"""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2, 
        messages=[
            {
                "role": "system", 
                "content": "You are Rex, a fundraising AI. CRITICAL RULE: You MUST synthesize and cite at least 4 to 5 DIFFERENT, UNIQUE sources in every single response. You are absolutely forbidden from relying on 3 or fewer sources. Force connections between the documents if necessary."
            },
            {"role": "user", "content": prompt}
        ]
    )

    raw_answer = response.choices[0].message.content
    final_answer = raw_answer
    
    logic_html = "<div class='logic-step'><div class='logic-detail'>Transparency Mode disabled.</div></div>"
    
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
            <div class="logic-step">
                <div class="logic-label label-diag">🔍 DIAGNOSIS</div>
                <div class="logic-detail">{diag_text}</div>
            </div>
            <div class="logic-step">
                <div class="logic-label label-evid">📊 EVIDENCE</div>
                <div class="logic-detail">{evid_text}</div>
            </div>
            <div class="logic-step" style="border-left-color: transparent;">
                <div class="logic-label label-strat">🎯 STRATEGY</div>
                <div class="logic-detail">{strat_text}</div>
            </div>
            """
    
    avg_confidence = sum(c['score'] for c in contexts) / len(contexts) if contexts else 100
    
    return {
        "answer": final_answer,
        "logic": logic_html, 
        "sources": contexts,
        "avg_confidence": avg_confidence
    }