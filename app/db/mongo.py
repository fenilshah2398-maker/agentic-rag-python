"""
MongoDB client shared by order tools (and optional direct collection access).

Uses AsyncMongoClient so FastAPI / LangGraph async tools can await queries
without blocking the event loop.

Collections:
  orders         → structured order rows (seed_orders.py)
  policy_chunks  → embedded policy text (also used via LangChain vector_store)
"""

from pymongo import AsyncMongoClient

from app.config import settings


# One shared client for the process (connection pooling)
client = AsyncMongoClient(
    settings.mongodb_uri
)

# Database name from .env (e.g. langchain_rag on Atlas)
db = client[settings.mongodb_database]

# Handle used by app/tools/order_tools.py
orders_collection = db["orders"]

# Available for direct async access; RAG path usually uses vector_store instead
policy_collection = db["policy_chunks"]
