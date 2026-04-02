# ---------- vectorize_research.py ----------
import os
import fitz  # PyMuPDF
from openai import OpenAI
from pinecone import Pinecone
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("reportingxpress")

def check_for_vendor_bias(text_sample):
    """
    Addresses Client Note: "Avoid research sources centered around a specific company's product."
    Uses a cheap, fast AI call to act as a bias filter before processing.
    """
    prompt = f"""
    Analyze the following excerpt from a fundraising document. 
    Does this text read like an objective academic/industry research paper, 
    or does it read like a biased sales pitch/whitepaper for a specific vendor's software?
    Reply with ONLY 'OBJECTIVE' or 'BIASED'.
    
    Excerpt: {text_sample[:1500]}
    """
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def process_research_directory(directory_path="research_docs"):
    """Scans a folder, filters out the playbook, checks for bias, and chunks the text."""
    
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)
        print(f"Created '{directory_path}' folder. Please add your PDFs here.")
        return

    # Addresses Client Note: "Larger chunk sizes and adjustments to overlap"
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,   # Increased from the default ~800
        chunk_overlap=200, # 200 character overlap ensures sentences aren't cut in half
        separators=["\n\n", "\n", ".", " ", ""]
    )

    for filename in os.listdir(directory_path):
        if not filename.endswith(".pdf"):
            continue
            
        # Addresses Client Note: "The playbook document... should not be used"
        if "playbook" in filename.lower():
            print(f"🚨 BLOCKED: '{filename}' - Playbooks are restricted by Joel.")
            continue

        filepath = os.path.join(directory_path, filename)
        print(f"\nScanning: {filename}")
        
        doc = fitz.open(filepath)
        full_text = "".join([page.get_text("text") for page in doc])
        
        # Run the Bias Check
        bias_result = check_for_vendor_bias(full_text)
        if "BIASED" in bias_result.upper():
            print(f"⚠️ SKIPPED: '{filename}' - Flagged for excessive vendor bias.")
            continue
            
        print("✅ Passed Bias Check. Vectorizing...")
        
        # Split text with overlap
        chunks = text_splitter.split_text(full_text)
        
        vectors = []
        for i, chunk in enumerate(chunks):
            response = openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=chunk
            )
            
            # Generate a clean citation ID (e.g., "Research_Paper_Part_1")
            clean_name = filename.replace(".pdf", "").replace(" ", "_")
            chunk_id = f"{clean_name}_Part_{i}"
            
            vectors.append({
                "id": chunk_id,
                "values": response.data[0].embedding,
                "metadata": {
                    "text": chunk,
                    "citation_id": f"{clean_name} (Section {i+1})",
                    "source": "Academic Research"
                }
            })
            
        # Batch upload to Pinecone
        if vectors:
            index.upsert(vectors=vectors, namespace="__default__")
            print(f"Successfully uploaded {len(vectors)} overlapping chunks for {filename}.")

if __name__ == "__main__":
    process_research_directory()