"""
MongoDB Atlas Vector Store — persistence layer for policy RAG.

Requires MongoDB Atlas (not local mongod):
  $vectorSearch only works on Atlas.

Configured names (must stay in sync with Atlas UI / create_vector_search_index):
  Database:   settings.mongodb_database  → langchain_rag
  Collection: policy_chunks
  Index:      policy_vector_index
  Embedding:  Gemini model from app.rag.embeddings (3072-d)

Used by:
  - scripts/ingest_policies.py → aadd_documents(chunks)
  - app/rag/retriever.py        → as_retriever(...) for online search
"""

from langchain_mongodb import MongoDBAtlasVectorSearch

from app.config import settings
from app.rag.embeddings import embeddings


vector_store = MongoDBAtlasVectorSearch.from_connection_string(
    # Atlas SRV URI from .env (mongodb+srv://...)
    connection_string=settings.mongodb_uri,
    # "db.collection" namespace for LangChain Mongo integration
    namespace=f"{settings.mongodb_database}.policy_chunks",
    # Same embedding model used at ingest time MUST be used at query time
    embedding=embeddings,
    # Atlas Vector Search index name (create once with dims=3072)
    index_name="policy_vector_index",
)
