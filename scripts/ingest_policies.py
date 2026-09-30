"""
Offline RAG indexing script — load policies, chunk, embed, store in Atlas.

Run from project root:
  python -m scripts.ingest_policies

Pipeline:
  data/policies/*.md
    → load_policy_documents()
    → split_documents()
    → vector_store.aadd_documents()  (Gemini embed + write to policy_chunks)

Atlas requirements:
  - MONGODB_URI must be mongodb+srv Atlas (not localhost)
  - Vector Search index name used by the app: policy_vector_index
  - Embedding dimensions must match index (3072 for gemini-embedding-001)

WARNING:
  This script APPENDS chunks. Re-running without clearing policy_chunks
  creates duplicates (4 → 8 → 12...). Clear the collection first if you
  need a clean re-index.
"""

import asyncio

from app.rag.ingestion import (
    load_policy_documents,
    split_documents,
)

from app.rag.vector_store import vector_store


async def ingest():
    """Chunk local markdown policies and upsert vectors into Atlas."""

    # Step 1: read markdown files into LangChain Documents
    documents = load_policy_documents()

    print(
        f"Loaded {len(documents)} documents"
    )

    # Step 2: split into overlapping chunks for better retrieval
    chunks = split_documents(documents)

    print(
        f"Created {len(chunks)} chunks"
    )

    # Step 3: embed each chunk and write to langchain_rag.policy_chunks
    await vector_store.aadd_documents(chunks)

    print("Policies indexed successfully")


if __name__ == "__main__":
    asyncio.run(ingest())
