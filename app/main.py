"""
FastAPI entrypoint for the Enterprise Agentic RAG app.

This file is the HTTP door only:
  - receive a chat request from the client
  - build the initial LangGraph state
  - run the compiled agent graph
  - return the final natural-language answer

It does NOT contain business logic. That lives in:
  app/agent/   → graph orchestration (THINK / DECIDE / DO)
  app/tools/   → Mongo order queries + policy RAG tool
  app/rag/     → LLM, embeddings, vector store, chunking

Typical request:
  POST /chat
  {
    "user_id": "USER-001",
    "message": "What did I order today?"
  }
"""

from fastapi import FastAPI

# HumanMessage = one user turn in LangChain/LangGraph message format
from langchain_core.messages import HumanMessage

# Compiled graph from graph.py: START → agent ⇄ tools → END
from app.agent.graph import graph

# Pydantic body schema: validates { "user_id", "message" } and powers /docs
from app.models.request import ChatRequest


# ASGI application object. uvicorn runs: uvicorn app.main:app
app = FastAPI(
    title="Enterprise Agentic RAG"
)


@app.get("/health")
async def health():
    """
    Liveness/readiness ping for load balancers or quick checks.
    Does not call Gemini, MongoDB, or the agent graph.
    """

    return {
        "status": "ok"
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Main chat endpoint — one user question in, one agent answer out.

    Detailed flow:
      1. FastAPI parses/validates JSON into ChatRequest
      2. We create AgentState:
           messages = [HumanMessage(user text)]
           user_id  = request.user_id  (trusted; later InjectedState into tools)
      3. graph.ainvoke(...) runs:
           agent (LLM) → maybe tools (ToolNode) → agent → ... → END
      4. result["messages"] holds the full transcript
      5. We return only the last message content as {"answer": "..."}
    """

    # ainvoke = async run of the whole LangGraph (compatible with FastAPI async)
    # Keys here MUST match AgentState in app/agent/state.py
    result = await graph.ainvoke(
        {
            # Start the conversation with the user's question
            "messages": [
                HumanMessage(
                    content=request.message
                )
            ],
            # Server-side identity. Order tools inject this via InjectedState.
            # Never rely on the LLM to supply the correct user_id.
            "user_id": request.user_id,
        }
    )

    # Full history may look like:
    #   [HumanMessage, AIMessage(tool_calls), ToolMessage, AIMessage(final text)]
    # The last item after END is the final AI answer.
    final_message = result["messages"][-1]

    return {
        "answer": final_message.content
    }
