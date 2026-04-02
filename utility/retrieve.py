
#This file is responsible for retrieving relevant information from the Pinecone index based on a user's query.  
# It converts the query into an embedding using OpenAI's API and then 
# searches the Pinecone index for the most relevant results, which are then displayed to the user.

#A simplified version of the retrieval logic used to 
# test if Pinecone is returning the right documents for a given query.

import os
from openai import OpenAI
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()

# Initialize clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

index = pc.Index("reportingxpress")

# Ask a question
query = input("Ask a question: ")

# Convert question to embedding
response = openai_client.embeddings.create(
    model="text-embedding-3-small",
    input=query
)

query_embedding = response.data[0].embedding

# Search Pinecone
results = index.query(
    vector=query_embedding,
    top_k=5,
    include_metadata=True
)

print("\nTop Results:\n")

for match in results["matches"]:
    print("Score:", match["score"])
    print(match["metadata"]["text"])
    print("\n---\n")