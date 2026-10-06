# Agentic RAG customer support

A signed-in user chats with an agent that can look up their orders in MongoDB
and answer policy questions from a vector store. The last 5 answers per user
are cached in Redis.

## Architecture

Browser (React, port 5173)
  HTTP /auth/*          sign up, sign in, sign out
  WebSocket /ws/chat    questions and answers
        |
        v
FastAPI (port 8000)
  session token in Redis  ->  user_id
  question hash in Redis  ->  last 5 answers
  LangGraph agent         ->  order tool or policy search
        |
        +-- MongoDB Atlas (users, orders, policy chunks)
        +-- Gemini (chat model and embeddings)

The chat page never sends user_id. The server reads it from the session token.

## Project map

app/main.py            HTTP routes and the chat WebSocket
app/auth/              password hash, Redis session, sign-in routes
app/chat/service.py    cache check, then the agent
app/cache/chat_cache.py  last 5 answers per user
app/agent/             LangGraph: think, tools, answer
app/tools/             order lookup and policy search
app/rag/               embeddings, chunking, vector store
frontend/src/pages/    sign-in page and chat page
frontend/src/chat/     WebSocket hook; transcript saved in localStorage

## Setup

Python 3.11+, Node 20+, a running Redis, and a MongoDB Atlas cluster.

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

Copy `.env.example` to `.env` and fill in the values.

## Run

Terminal 1, project root:

uvicorn app.main:app --reload

Terminal 2:

cd frontend
npm install
npm run dev

Open http://localhost:5173
Sign up, then ask: "What is the refund policy?"
Ask the same question again. The reply is marked "From cache".

Load demo orders (optional):

python -m scripts.seed_orders

Those rows belong to USER-8624C7. A newly signed-up user has a different id,
so order questions for that new user return no rows until orders exist for them.
Policy questions work for every user.

Index the policy documents once:

python -m scripts.ingest_policies