import os
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("officialreportingxpress")

print("Flushing all records from the Pinecone index...")

# Delete all vectors in the default namespace
index.delete(delete_all=True, namespace="__default__")

print("✅ Index successfully cleared! You are ready to run the new vectorize script.")