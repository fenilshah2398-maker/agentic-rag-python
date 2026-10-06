# """
# FastAPI entrypoint for the Enterprise Agentic RAG app.

# This file is the HTTP door only:
#   - receive a chat request from the client
#   - build the initial LangGraph state
#   - run the compiled agent graph
#   - return the final natural-language answer

# It does NOT contain business logic. That lives in:
#   app/agent/   → graph orchestration (THINK / DECIDE / DO)
#   app/tools/   → Mongo order queries + policy RAG tool
#   app/rag/     → LLM, embeddings, vector store, chunking

# Typical request:
#   POST /chat
#   {
#     "user_id": "USER-001",
#     "message": "What did I order today?"
#   }
# """
# #uvicorn app.main:app --reload
# from fastapi import FastAPI
# from app.cache.chat_cache import get_cached_answer, question_hash, save_answer

# # HumanMessage = one user turn in LangChain/LangGraph message format
# from langchain_core.messages import HumanMessage

# # Compiled graph from graph.py: START → agent ⇄ tools → END
# from app.agent.graph import graph

# # Pydantic body schema: validates { "user_id", "message" } and powers /docs
# from app.models.request import ChatRequest


# # ASGI application object. uvicorn runs: uvicorn app.main:app
# app = FastAPI(
#     title="Enterprise Agentic RAG"
# )


# @app.get("/health")
# async def health():
#     """
#     Liveness/readiness ping for load balancers or quick checks.
#     Does not call Gemini, MongoDB, or the agent graph.
#     """

#     return {
#         "status": "ok"
#     }


# @app.post("/chat")
# async def chat(request: ChatRequest):
    
#     """
#     Main chat endpoint — one user question in, one agent answer out.

#     Detailed flow:
#       1. FastAPI parses/validates JSON into ChatRequest
#       2. We create AgentState:
#            messages = [HumanMessage(user text)]
#            user_id  = request.user_id  (trusted; later InjectedState into tools)
#       3. graph.ainvoke(...) runs:
#            agent (LLM) → maybe tools (ToolNode) → agent → ... → END
#       4. result["messages"] holds the full transcript
#       5. We return only the last message content as {"answer": "..."}
#     """
#     """
#     One user question in, one answer out.
#     Cache check happens before the agent. A repeated question for the
#     same user returns the saved text and never calls Gemini or MongoDB.
#     """
#     q_hash = question_hash(request.user_id, request.message)
#     cached = await get_cached_answer(request.user_id, q_hash)
#     if cached is not None:
#         return {
#             "answer": cached,
#             "cached": True,
#         }
#     # ainvoke = async run of the whole LangGraph (compatible with FastAPI async)
#     # Keys here MUST match AgentState in app/agent/state.py
#     result = await graph.ainvoke(
#         {
#             # Start the conversation with the user's question
#             "messages": [
#                 HumanMessage(
#                     content=request.message
#                 )
#             ],
#             # Server-side identity. Order tools inject this via InjectedState.
#             # Never rely on the LLM to supply the correct user_id.
#             "user_id": request.user_id,
#         }
#     )

#     # Full history may look like:
#     #   [HumanMessage, AIMessage(tool_calls), ToolMessage, AIMessage(final text)]
#     # The last item after END is the final AI answer.
#     final_message = result["messages"][-1]
#     answer = final_message.content
#     await save_answer(
#         request.user_id,
#         q_hash,
#         request.message,
#         answer,
#     )
#     return {
#         "answer": answer,
#         "cached": False,
#     }

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage

from app.auth.routes import router as auth_router
from app.auth.sessions import get_user_id
from app.chat.service import answer_question
from app.db.mongo import users_collection
from app.models.request import ChatRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One email can register only once. Mongo enforces that.
    await users_collection.create_index("email", unique=True)
    yield


app = FastAPI(
    title="Enterprise Agentic RAG",
    lifespan=lifespan,
)

# The React dev server runs on port 5173. This lets the browser call port 8000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(request: ChatRequest):
    """Swagger path. The React chat page uses the socket instead."""
    return await answer_question(request.user_id, request.message)


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    """
    One long-lived connection per open chat page.

    Message order:
      1. Browser sends  {"type": "auth", "token": "..."}
      2. Server replies {"type": "ready"} after Redis recognizes the token
      3. Browser sends  {"type": "question", "message": "..."}
      4. Server sends   {"type": "status", "text": "thinking"}
      5. Server sends   {"type": "answer", "answer": "...", "cached": false}

    user_id comes from the token. A question message is not allowed to
    include a user id.
    """
    await websocket.accept()
    user_id = None

    try:
        while True:
            data = json.loads(await websocket.receive_text())
            kind = data.get("type")

            if user_id is None:
                if kind != "auth":
                    await websocket.close(code=1008)
                    return

                user_id = await get_user_id(data.get("token", ""))
                if user_id is None:
                    await websocket.send_json(
                        {"type": "error", "text": "Sign in again."}
                    )
                    await websocket.close(code=1008)
                    return

                await websocket.send_json({"type": "ready"})
                continue

            if kind != "question":
                continue

            message = str(data.get("message", "")).strip()
            if not message:
                await websocket.send_json(
                    {"type": "error", "text": "Type a question first."}
                )
                continue

            await websocket.send_json({"type": "status", "text": "thinking"})
            payload = await answer_question(user_id, message)
            await websocket.send_json({"type": "answer", **payload})

    except WebSocketDisconnect:
        return
    except json.JSONDecodeError:
        await websocket.close(code=1003)