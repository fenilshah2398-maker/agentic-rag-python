"""
Embedding model — turns text into dense vectors for RAG.

Used in two places:
  OFFLINE (ingest):  each policy chunk → vector → stored in Atlas policy_chunks
  ONLINE  (search):  user/tool query   → vector → $vectorSearch nearest neighbors

Current model (from .env): gemini-embedding-001
Vector size observed for this project: 3072 dimensions
(Atlas vector index policy_vector_index must match that dimension.)
"""

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.config import settings


embeddings = GoogleGenerativeAIEmbeddings(
    model=settings.gemini_embedding_model,
    google_api_key=settings.gemini_api_key,
)

# Optional smoke-check on import: proves the API key + model work.
# Safe to remove in production to avoid an extra embedding call at startup.
vector = embeddings.embed_query(
    "What is the refund policy?"
)
