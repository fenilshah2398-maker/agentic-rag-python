"""
Policy tool — this is the RAG tool inside the agent.

Flow when the LLM calls search_policy(query="..."):
  1. ToolNode executes this function
  2. retriever embeds the query (Gemini embeddings)
  3. Atlas $vectorSearch finds nearest chunks in policy_chunks
     using index name: policy_vector_index
  4. We return plain text + source filename for the LLM to cite

Difference vs order tools:
  - Orders = exact Mongo filters (structured)
  - Policies = semantic similarity (unstructured RAG)
"""

from langchain_core.tools import tool

from app.rag.retriever import retriever


@tool
async def search_policy(query: str):
    """
    Search company policy documents for information
    about cancellation, refund, delivery and returns.

    The LLM chooses `query` (e.g. "refund processing time").
    Good queries are short and topical — the retriever embeds them.
    """

    # ainvoke runs async similarity search (top-k configured in retriever.py)
    documents = await retriever.ainvoke(query)

    # Convert LangChain Documents → simple dicts for the LLM / ToolMessage
    # page_content = chunk text; metadata["source"] = e.g. "refund.md"
    return [
        {
            "content": document.page_content,
            "source": document.metadata.get(
                "source"
            ),
        }
        for document in documents
    ]
