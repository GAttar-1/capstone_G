import os
from pinecone import Pinecone
from dotenv import load_dotenv

# Load your environment variables
load_dotenv()

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("reportingxpress")

def check_metadata():
    print("Fetching a sample record from Pinecone...")
    
    # CHANGED: Use 0.1 instead of 0.0 to prevent cosine similarity math errors
    dummy_vector = [0.1] * 1536 
    
    try:
        # CHANGED: Added the namespace parameter
        results = index.query(
            vector=dummy_vector,
            top_k=1,
            include_metadata=True,
            namespace="__default__" 
        )
        
        if not results["matches"]:
            print("No records found in the index.")
            return
            
        # Extract the first match
        sample_match = results["matches"][0]
        
        print("\n--- SAMPLE RECORD ---")
        print(f"Pinecone Vector ID (Chunk ID): {sample_match['id']}")
        
        if "metadata" in sample_match and sample_match["metadata"]:
            print("\n--- METADATA KEYS ---")
            metadata = sample_match["metadata"]
            
            # Print each key and a snippet of its value
            for key, value in metadata.items():
                # Truncate long text for readability
                val_str = str(value)
                if len(val_str) > 50:
                    val_str = val_str[:50] + "..."
                print(f"- {key}: {val_str}")
        else:
            print("\nNo metadata found on this record.")
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    check_metadata()