# Reporting Xpress (RX) | CI Hub

## Overview
Reporting Xpress (RX) is a professional, AI-driven fundraising assistant that provides evidence-based recommendations to non-technical users. Employing a Retrieval-Augmented Generation (RAG) pipeline, it connects a curated knowledge base of donor research and internal analytics to a seamless Streamlit chat interface.

## Technical Infrastructure
- **Frontend / UI**: Streamlit (`app.py`) layered with a custom Figma-matched CSS injection to create a robust chat interface and analytics dashboard.
- **LLM & Generation**: OpenAI `gpt-4o-mini`
- **Embeddings**: OpenAI `text-embedding-3-small`
- **Vector Database**: Pinecone
  - Index Name: `officialreportingxpress`
  - Dimensions: 1536
  - Metric: Cosine Similarity
- **Document Processing**: `PyMuPDF` (`fitz`) and LangChain's `RecursiveCharacterTextSplitter`.

## Key Files & Directory Structure

```text
c:\Users\gabri\OneDrive\Desktop\reportingxpress1\
├── app.py                     # Main Streamlit frontend. Handles chat UI, layout, and calling rag_pipeline.
├── rag_pipeline.py            # RAG execution engine. Contains Pinecone retrieval and strict AI completion prompting.
├── vectorize_pdf.py           # Ingestion pipeline. Processes raw PDFs from Research_docs and uploads to Pinecone.
├── benchmark.py               # Evaluation suite. Runs automated queries to test AI outputs against the vector DB.
├── context.md                 # Project directives and Sprint checklist.
├── .env                       # Environment variables (OpenAI & Pinecone credentials).
├── Research_docs/             # Source PDFs ingested into the pipeline.
│   ├── CI_Hub_Analytics_Catalog Version for RAG (2).pdf
│   ├── PreventDonorAttrition (1).pdf
│   └── (16 other industry-standard reports and whitepapers)
├── utility/                   # Developer tools and utility scripts.
│   ├── clear_index.py         # Flushes all Pinecone vectors when ingestion schema changes.
│   ├── check_metadata.py      # Audits existing metadata in Pinecone.
│   └── retrieve.py            # Manual retrieval testing outside of the Streamlit UI.
└── legacy_files/              # Outdated or deprecated scripts.
```

## Core Architecture

### 1. Ingestion Engine (`vectorize_pdf.py`)
Vectorizes PDFs to Pinecone. The ingestion engine is currently being upgraded for Sprint 4 to include:
- A regex-based "Example Data Scrubber" to prevent the LLM from treating hypothetical numerical values as factual analytics.
- Custom slicing for the "Analytics Catalog," which forces Pinecone to treat individual analytic definitions (i.e., 'QX123') as distinct, standalone documents via metadata spoofing.
- Title page purging.

### 2. Retrieval & Generation (`rag_pipeline.py`)
Retrieves knowledge using Pinecone embeddings. To ensure high-quality and un-biased responses, the RAG engine retrieves a massive chunk net (top 60) and applies logic to enforce retrieving deeper document pages. The strict `gpt-4o-mini` system prompt mandates that constraints are met, such as citing specific combinations of research documents and analytic sources.

### 3. Application Frontend (`app.py`)
Powered by Streamlit, but heavily augmented by a custom injected CSS layout to mimic a customized web app UI. Features include:
- Session history uploads/downloads.
- AI Transparency mode outlining the "Diagnosis, Evidence, Strategy" reasoning.
- Side-by-side RAG Insights that provide active analytics on model confidence and retrieved sources.

## Current Sprint (Sprint 4) Focus
The team is actively polishing the Streamlit UI (fixing CSS overlapping/truncation issues with the sidebars and panels) and upgrading the PDF ingestion pipeline to enforce rigorous formatting restrictions (like the QX Catalog Slicer).
