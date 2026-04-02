r"""
=========================================================================================
REPORTING XPRESS: AI INGESTION PIPELINE
File: vectorize_pdf.py
Description: Ingests, processes, and vectorizes documents into the Pinecone Vector Database.

CLIENT ALIGNMENT (March 17th Meeting Minutes):
-----------------------------------------------------------------------------------------
1. Restricted Data Safeguard: Blocks any file containing "playbook".
2. Knowledge Buckets: Uses LLM (scanning up to the first 10 pages) to sort.
3. Grammar-Aware Chunking: Uses RecursiveCharacterTextSplitter with RegEx (?<=\. ) 
   to ensure sentences are not broken awkwardly across chunks.
4. Page-Level Citations: Bypasses QX codes for strict Document Name + Page Number citations.
5. Smart Caching: Skips files that have already been vectorized (Task 2).
=========================================================================================
"""

import os
import fitz  # PyMuPDF
from openai import OpenAI
from pinecone import Pinecone
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

# Initialize clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("officialreportingxpress")

REGISTRY_FILE = "vectorized_registry.txt"

def load_processed_files():
    """Loads the list of already vectorized files from the local registry."""
    if not os.path.exists(REGISTRY_FILE):
        return set()
    with open(REGISTRY_FILE, "r") as f:
        return set(line.strip() for line in f)

def mark_file_as_processed(filename):
    """Adds a successfully vectorized file to the local registry."""
    with open(REGISTRY_FILE, "a") as f:
        f.write(f"{filename}\n")

def assign_bucket_with_ai(text_sample):
    """
    Uses AI to classify the document into exactly one of the 4 client buckets.
    Reads a large sample (up to ~15,000 characters) to ensure high accuracy.
    """
    prompt = f"""
    Analyze the following text excerpt from a document.
    Categorize it into EXACTLY ONE of these four knowledge buckets:
    - Reports
    - Research Papers
    - Fundraising Information / Blogs
    - Navigation / Best Practices

    Respond with ONLY the name of the bucket. Do not include punctuation, quotes, or extra text.

    Text Sample:
    {text_sample[:15000]}
    """
    
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0 # Strict output
    )
    
    return response.choices[0].message.content.strip()

def process_pdf_directory(directory_path="research_docs"):
    """
    Scans a folder, extracts text, uses AI to classify the document, 
    and vectorizes it using grammar-aware page-by-page chunking.
    """
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)
        print(f"Created '{directory_path}'. Please drop your PDFs in there.")
        return

    # Load the registry of already processed files
    processed_files = load_processed_files()

    # Grammar-Aware Chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
        separators=["\n\n", "\n", r"(?<=\. )", " ", ""],
        is_separator_regex=True
    )

    for filename in os.listdir(directory_path):
        if not filename.endswith(".pdf"):
            continue
            
        # Playbook Exclusion (Client Requirement)
        if "playbook" in filename.lower():
            print(f"🚨 BLOCKED: '{filename}' - Playbooks are restricted by Joel.")
            continue
            
        # --- NEW: Smart Caching Check ---
        if filename in processed_files:
            print(f"⏭️ SKIPPED: '{filename}' - Already vectorized in Pinecone.")
            continue
            
        filepath = os.path.join(directory_path, filename)
        base_name = filename.replace(".pdf", "").replace("_", " ")
        
        doc = fitz.open(filepath)
        
        # 10-Page Deep Scan
        sample_text = ""
        # min() ensures it doesn't crash if a PDF is only 3 pages long
        pages_to_scan = min(10, len(doc)) 
        for p in range(pages_to_scan):
            sample_text += doc[p].get_text("text") + "\n"
            
        bucket = assign_bucket_with_ai(sample_text.strip())
        
        print(f"\nScanning: {base_name} | AI Assigned Bucket: [{bucket}]")
        
        vectors = []
        
        # Iterate page-by-page to preserve exact page numbers
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()
            
            if not text:
                continue
                
            # Split the text safely using grammar rules
            chunks = text_splitter.split_text(text)
            
            for i, chunk in enumerate(chunks):
                response = openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=chunk
                )
                
                actual_page = page_num + 1
                citation_id = f"{base_name} (Page {actual_page})"
                unique_chunk_id = f"{filename}_p{actual_page}_c{i}"
                
                vectors.append({
                    "id": unique_chunk_id,
                    "values": response.data[0].embedding,
                    "metadata": {
                        "text": chunk,
                        "citation_id": citation_id,
                        "knowledge_bucket": bucket,
                        "source_file": base_name,
                        "page_number": actual_page
                    }
                })
                
        # Batch upload to Pinecone
        if vectors:
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                index.upsert(vectors=vectors[i:i + batch_size], namespace="__default__")
            
            print(f"✅ Vectorized {len(vectors)} chunks into [{bucket}].")
            
            # --- NEW: Log as Processed ---
            mark_file_as_processed(filename)

if __name__ == "__main__":
    process_pdf_directory("research_docs")