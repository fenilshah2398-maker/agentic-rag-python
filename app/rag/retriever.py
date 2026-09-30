"""
Retriever — thin wrapper over the vector store for online RAG.

as_retriever() exposes a LangChain Retriever interface so tools can call:
  await retriever.ainvoke(query)

search_kwargs:
  k=4 → return the 4 most similar policy chunks for each query.
  Tune k up for broader context, down for shorter / cheaper prompts.
"""

from app.rag.vector_store import vector_store


retriever = vector_store.as_retriever(
    search_kwargs={
        "k": 4
    }
)
