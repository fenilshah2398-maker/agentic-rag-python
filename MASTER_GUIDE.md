# Agentic RAG Master Guide

> One document to deeply understand **this project**, the **theory** behind RAG + agents, **why the code is written this way**, and the **exact execution flow**.
>
> Project label: **AI Agent + RAG + LangGraph**
>
> Stack: FastAPI + LangGraph + Gemini + **MongoDB Atlas** (orders + vector search)

---

## Table of Contents

1. [Big Picture — What You Are Building](#1-big-picture--what-you-are-building)
2. [Theory — RAG vs Agentic RAG](#2-theory--rag-vs-agentic-rag)
3. [Theory — Agents, Tools, Graphs](#3-theory--agents-tools-graphs)
4. [Project Map — Folders & Why They Exist](#4-project-map--folders--why-they-exist)
5. [Data Layer — Two Knowledge Sources](#5-data-layer--two-knowledge-sources)
6. [RAG Pipeline — Offline Indexing](#6-rag-pipeline--offline-indexing)
7. [Agent Core — State, Nodes, Graph](#7-agent-core--state-nodes-graph)
8. [Full Execution Flow (Step by Step)](#8-full-execution-flow-step-by-step)
9. [Walkthrough With a Real Request](#9-walkthrough-with-a-real-request)
10. [Why Code Is Written This Way](#10-why-code-is-written-this-way)
11. [Security Pattern — Never Trust LLM for user_id](#11-security-pattern--never-trust-llm-for-user-id)
12. [Common Bugs You Already Hit (And Why)](#12-common-bugs-you-already-hit-and-why)
13. [Message Types Cheat Sheet](#13-message-types-cheat-sheet)
14. [How To Debug Like a Pro](#14-how-to-debug-like-a-pro)
15. [Mental Model To Master This Stack](#15-mental-model-to-master-this-stack)
16. [What To Learn Next](#16-what-to-learn-next)
17. [Current Environment & Atlas Setup](#17-current-environment--atlas-setup)

---

## 1. Big Picture — What You Are Building

This app answers questions like:

- “What did I order today?” → **MongoDB orders** (structured data)
- “What is the refund policy?” → **Vector search over policy docs** (unstructured RAG)
- “Can I cancel ORD-1002 and get a refund?” → **Both tools** (agentic RAG)

```
Client (Swagger / curl)
        │
        ▼
   FastAPI /chat
        │
        ▼
   LangGraph Agent
   ┌─────────────────────────────┐
   │  THINK (LLM + tools bound)  │
   │  DECIDE (should_continue)   │
   │  DO (ToolNode runs tools)   │
   │  loop until final answer    │
   └─────────────────────────────┘
        │              │
        ▼              ▼
   Order tools     Policy tool
   (Mongo find)    (vector retrieve)
```

**Key idea:** The LLM does **not** know your orders or policies by heart. It **decides** which tool to call. Your Python code **runs** the tool. Then the LLM reads the result and answers.

---

## 2. Theory — RAG vs Agentic RAG

### Classic RAG (Retrieval-Augmented Generation)

One fixed path:

```
User question
  → embed question
  → vector search top-k chunks
  → stuff chunks into prompt
  → LLM answers
```

Good when **every** question needs the same knowledge base (e.g. only docs).

### Agentic RAG (What This Project Uses)

The model is an **agent**: it can choose zero, one, or many tools.

```
User question
  → LLM thinks
  → maybe call get_today_orders
  → maybe call search_policy
  → maybe call both
  → LLM answers from tool results
```

| | Classic RAG | Agentic RAG |
|---|---|---|
| Path | Fixed | Dynamic (LLM chooses) |
| Data sources | Usually one vector DB | Many tools (DB, APIs, search…) |
| Control | You hardcode retrieve→generate | Graph: think → decide → do → think |
| Best for | Single knowledge domain | Mixed: orders + policies + more |

**RAG inside this agent:** the `search_policy` tool **is** RAG. The agent decides *when* to use it.

---

## 3. Theory — Agents, Tools, Graphs

### Tool

A normal Python function wrapped so the LLM can call it by name.

```python
@tool
async def get_today_orders(...):
    """Docstring becomes the tool description the LLM reads."""
```

The LLM never executes MongoDB itself. It only outputs:

> “I want to call `get_today_orders`”

Your runtime (`ToolNode`) executes the real function.

### Agent

An LLM that:

1. Sees a system prompt (rules)
2. Sees conversation / tool results
3. Either returns a final text answer **or** requests tool calls

### Graph (LangGraph)

A state machine:

- **Nodes** = steps (agent, tools)
- **Edges** = what runs next
- **Conditional edges** = branch based on state (`should_continue`)
- **State** = shared memory that travels through the graph

Your loop:

```
THINK → DECIDE → DO → THINK → DECIDE → DONE
 agent   should_   tools  agent   should_
         continue                 continue → END
```

---

## 4. Project Map — Folders & Why They Exist

```
agentic-rag-python/
├── app/
│   ├── main.py              # HTTP API entry (FastAPI)
│   ├── config.py            # Loads .env settings
│   ├── models/              # Request/response schemas
│   ├── db/mongo.py          # Mongo client + collections
│   ├── rag/                 # Offline + online RAG pieces
│   │   ├── llm.py           # Chat model (Gemini)
│   │   ├── embeddings.py    # Embedding model
│   │   ├── vector_store.py  # MongoDB Atlas vector search
│   │   ├── ingestion.py     # Load + chunk markdown policies
│   │   └── retriever.py     # top-k retriever for tools
│   ├── tools/               # What the agent can DO
│   │   ├── order_tools.py   # Structured DB queries
│   │   └── policy_tools.py  # RAG search tool
│   └── agent/               # Brain of the system
│       ├── state.py         # Shared state shape
│       ├── nodes.py         # agent_node + tool list + prompt
│       └── graph.py         # Wire nodes + edges + compile
├── data/policies/           # Source policy markdown
├── scripts/
│   ├── seed_orders.py       # Insert demo orders
│   └── ingest_policies.py   # Chunk + embed + store policies
└── .env                     # Secrets and config
```

### Design rule used here

| Layer | Responsibility | Must NOT do |
|---|---|---|
| `main.py` | HTTP in/out | Business logic / Mongo queries |
| `agent/` | Orchestration | Know Mongo schema details |
| `tools/` | Side effects (DB, retrieve) | Decide conversation flow |
| `rag/` | Models + vectors | HTTP |
| `scripts/` | One-time setup | Run on every request |

This separation is how production agent systems stay maintainable.

---

## 5. Data Layer — Two Knowledge Sources

### A) Structured: Orders (MongoDB collection `orders`)

Seeded by `scripts/seed_orders.py`:

| order_id | user_id | product | note |
|---|---|---|---|
| ORD-1001 | USER-001 | MacBook Pro | today |
| ORD-1002 | USER-001 | iPhone 17 | today |
| ORD-1003 | USER-001 | Headphones | yesterday |

Queried by **filters** (`user_id`, date range, `order_id`) — not by embeddings.

### B) Unstructured: Policies (vector collection `policy_chunks`)

Source files in `data/policies/`:

- `refund.md`, `cancellation.md`, `delivery.md`, `return.md`

Ingested → split into chunks → embedded (`gemini-embedding-001`, **3072 dims**) → stored in Atlas collection `policy_chunks` with Atlas Vector Search index:

| Setting | Value |
|---|---|
| Database | `langchain_rag` |
| Collection | `policy_chunks` |
| **Vector search index name** | **`policy_vector_index`** |
| Defined in | `app/rag/vector_store.py` → `index_name="policy_vector_index"` |
| Embedding dims | `3072` |

Queried by **semantic similarity** (“refund timing” ≈ chunk about 5–7 business days).

**Why Atlas (not local Mongo)?**  
`$vectorSearch` works only on **MongoDB Atlas**. Local `mongodb://localhost:27017` will fail policy RAG with:  
`OperationFailure: $vectorSearch stage is only allowed on MongoDB Atlas`.

**Why two systems?**  
Orders are facts with exact IDs and dates. Policies are prose. Mixing both into one vector DB is usually worse than tools specialized per source.

---

## 6. RAG Pipeline — Offline Indexing

Runtime chat does **not** re-read markdown files. Indexing is offline.

### Step 1 — Load (`ingestion.py`)

```text
data/policies/*.md  →  LangChain Document(page_content, metadata)
```

### Step 2 — Split

```text
RecursiveCharacterTextSplitter(chunk_size=500, overlap=100)
```

- **chunk_size**: each piece small enough for embedding + context
- **overlap**: avoid cutting a rule in half with zero context

### Step 3 — Embed + Store (`ingest_policies.py` → `vector_store`)

```text
chunk text → Gemini embeddings (3072-d) → MongoDB Atlas collection policy_chunks
```

Then ensure Atlas Vector Search index exists:

```text
index name: policy_vector_index
(create once via vector_store.create_vector_search_index(dimensions=3072))
```

### Step 4 — Online retrieve (`retriever.py` + `search_policy` tool)

```text
user query → embed → nearest 4 chunks (k=4) via $vectorSearch on policy_vector_index → return to agent
```

```
OFFLINE (setup):
  MD files → chunk → embed → Atlas policy_chunks
  + Atlas index policy_vector_index

ONLINE (every policy question):
  query → retriever → chunks → tool result → LLM answer
```

**Important:** `scripts/ingest_policies.py` currently **appends** documents. Running it twice duplicates chunks (e.g. 4 → 8). Prefer clear-then-ingest, or delete `policy_chunks` before re-running.

---

## 7. Agent Core — State, Nodes, Graph

### 7.1 State (`app/agent/state.py`)

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: str
```

- **`messages`**: conversation history (human, AI, tool messages)
- **`add_messages`**: **append** new messages instead of replacing the list
- **`user_id`**: authenticated user from API payload (trusted)

Without `add_messages`, each node would wipe history. That breaks tool loops (you hit this bug earlier).

### 7.2 Agent node (`app/agent/nodes.py`) — THINK

```python
llm_with_tools = llm.bind_tools(tools)

async def agent_node(state):
    messages_with_system = [SystemMessage(SYSTEM_PROMPT), *state["messages"]]
    response = await llm_with_tools.ainvoke(messages_with_system)
    return {"messages": [response]}
```

What happens:

1. Prefixed system rules
2. Full message history (including previous tool results)
3. LLM either:
   - returns text (final answer), or
   - returns `tool_calls` (name + args)

`bind_tools(tools)` sends tool schemas to Gemini so it knows `get_today_orders`, `get_order_by_id`, `search_policy`.

### 7.3 Router (`should_continue` in `graph.py`) — DECIDE

```python
def should_continue(state):
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END
```

### 7.4 Tool node (`ToolNode`) — DO

```python
tool_node = ToolNode(tools)
graph_builder.add_node("tools", tool_node)
```

**This is the code that actually runs your tools** after the LLM names them.

`ToolNode` internally:

1. Reads last AI message’s `tool_calls`
2. Matches name → Python function
3. Injects `InjectedState` args (like `user_id`)
4. Awaits the function
5. Appends `ToolMessage` results to state

You do **not** write a manual `if name == "get_today_orders"` switch — `ToolNode` is that switch.

### 7.5 Graph wiring (`graph.py`)

```text
START → agent
agent → (conditional) tools | END
tools → agent          # always return to LLM with tool results
```

Compiled once at import:

```python
graph = graph_builder.compile()
```

---

## 8. Full Execution Flow (Step by Step)

```
┌──────────────────────────────────────────────────────────────┐
│ 1. CLIENT                                                    │
│    POST /chat  { "user_id": "USER-001", "message": "..." } │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. FastAPI main.py                                           │
│    Build initial state:                                      │
│      messages = [HumanMessage(content=message)]              │
│      user_id  = "USER-001"                                   │
│    await graph.ainvoke(state)                                │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. START → agent_node                                        │
│    LLM sees system prompt + human message + tool schemas     │
│    Output example:                                           │
│      AIMessage(tool_calls=[{name: "get_today_orders", ...}]) │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. should_continue                                           │
│    tool_calls present? → "tools"                             │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. ToolNode ("tools")                                        │
│    Runs get_today_orders(user_id injected from state)        │
│    MongoDB find → list of orders                             │
│    Appends ToolMessage(content=orders_json)                  │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ 6. edge tools → agent                                        │
│    agent_node again with history including ToolMessage       │
│    LLM writes final natural-language answer                  │
│    AIMessage(content="You ordered MacBook Pro and iPhone...")│
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ 7. should_continue                                           │
│    no tool_calls → END                                       │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ 8. main.py                                                   │
│    final_message = result["messages"][-1]                    │
│    return { "answer": final_message.content }                │
└──────────────────────────────────────────────────────────────┘
```

### Who runs what?

| Moment | Code that runs | File |
|---|---|---|
| HTTP arrives | `chat()` | `main.py` |
| LLM thinks | `agent_node` | `nodes.py` |
| Route decision | `should_continue` | `graph.py` |
| **Tool executes** | **`ToolNode`** | **`graph.py` + `order_tools.py` / `policy_tools.py`** |
| Mongo query | `orders_collection.find` | `order_tools.py` |
| Policy search | `retriever.ainvoke` | `policy_tools.py` → `retriever.py` |
| Final JSON | `chat()` return | `main.py` |

---

## 9. Walkthrough With a Real Request

### Request

```json
{
  "user_id": "USER-001",
  "message": "What did I order today?"
}
```

### Round 1 — THINK

State before agent:

```text
messages: [HumanMessage("What did I order today?")]
user_id: "USER-001"
```

LLM decides: need `get_today_orders` (no `user_id` arg in schema because of `InjectedState`).

### Round 1 — DO

`ToolNode` calls:

```text
get_today_orders(user_id="USER-001")  # injected from state, not from LLM
```

Mongo returns ORD-1001, ORD-1002 (not ORD-1003 — yesterday).

### Round 2 — THINK

LLM sees tool result and answers in plain English.

### Response

```json
{
  "answer": "Today you ordered a MacBook Pro (ORD-1001) and an iPhone 17 (ORD-1002)."
}
```

### Harder request (multi-tool)

```json
{
  "user_id": "USER-001",
  "message": "Can I get a refund for ORD-1001?"
}
```

Possible loop:

1. `get_order_by_id(order_id="ORD-1001")` → status DELIVERED
2. `search_policy(query="refund for delivered order")` → policy chunks
3. Final answer combining both

The agent may call tools in one step (parallel) or across multiple loops. Your graph supports both because tools always return to `agent`.

---

## 10. Why Code Is Written This Way

### Why FastAPI + graph.ainvoke?

API stays thin. All intelligence lives in the graph. Easy to test the graph without HTTP later.

### Why `bind_tools` instead of stuffing tool docs in the prompt manually?

Providers understand structured tool schemas. You get reliable `tool_calls` objects instead of fragile free-text “please call X”.

### Why `ToolNode` instead of calling tools inside `agent_node`?

Separation of roles:

- Agent node = pure reasoning
- Tool node = side effects

Also: LangGraph handles parallel tool calls, errors, and `InjectedState` for you.

### Why system prompt rules (“Never invent order information”)?

LLMs hallucinate. Tools + strict prompts reduce that. Still verify with tool results in debugging.

### Why async everywhere?

Mongo and Gemini calls are I/O bound. `async` / `ainvoke` keep the server scalable.

### Why temperature=0?

For factual enterprise assistants, low temperature = more deterministic answers.

---

## 11. Security Pattern — Never Trust LLM for user_id

### Wrong (what broke for you earlier)

```python
@tool
async def get_today_orders(user_id: str):
    ...
```

LLM invents `user_1234` because it never reliably saw `USER-001`.

### Right (current code)

```python
@tool
async def get_today_orders(
    user_id: Annotated[str, InjectedState("user_id")],
):
    ...
```

- `user_id` comes from API → graph state
- Hidden from the tool schema the model sees
- `ToolNode` injects it at runtime

**Enterprise rule:** identity, auth, tenant IDs = server-side injection. Never model-chosen.

Same idea for: `org_id`, permissions, API keys, “acting as admin” flags.

---

## 12. Common Bugs You Already Hit (And Why)

### Bug 1 — `ValueError: contents are required` after tools

**Cause:** `messages: list` without `add_messages` → each node **replaced** history.

Flow became:

```text
[Human] → replaced by [AI tool_calls] → replaced by [ToolMessage]
→ second LLM call had broken / empty conversation for Gemini
```

**Fix:**

```python
messages: Annotated[list, add_messages]
```

### Bug 2 — LLM used `user_1234` instead of `USER-001`

**Cause:** `user_id` was a normal tool argument.

**Fix:** `InjectedState("user_id")`.

### Bug 3 — “Today’s orders” missing ORD-1003

**Not a bug.** Seed puts ORD-1003 yesterday; `get_today_orders` filters `order_date` to today only.

### Bug 4 — Debugging with `--reload`

Reload + debugger can spawn child processes and skip breakpoints. Prefer debug launch **without** relying on reload when stepping carefully.

### Bug 5 — `$vectorSearch` only allowed on MongoDB Atlas

**Cause:** `.env` pointed at local Mongo (`mongodb://localhost:27017`) while code uses `MongoDBAtlasVectorSearch`.

**Fix:** Use Atlas `mongodb+srv://...` URI and database `langchain_rag`, with index **`policy_vector_index`** on `policy_chunks`. Restart the server after changing `.env`.

### Bug 6 — Duplicate policy chunks after re-ingest

**Cause:** `ingest_policies` only `aadd_documents` (no delete).

**Fix:** Clear `policy_chunks` before ingest, or update the script to delete-then-insert.

---

## 13. Message Types Cheat Sheet

| Type | Who creates it | Meaning |
|---|---|---|
| `SystemMessage` | Your `agent_node` | Rules / persona |
| `HumanMessage` | `main.py` from payload | User question |
| `AIMessage` | LLM | Final text and/or `tool_calls` |
| `ToolMessage` | `ToolNode` | Result of one tool call |

Typical successful transcript:

```text
1. HumanMessage: "What did I order today?"
2. AIMessage: tool_calls=[get_today_orders]
3. ToolMessage: [{order_id: ORD-1001, ...}, ...]
4. AIMessage: "You ordered MacBook Pro and iPhone 17."
```

Only step 4’s `.content` is returned by `/chat` today.

---

## 14. How To Debug Like a Pro

### Print / log style (like `console.log`)

```python
print("STATE USER", state["user_id"])
print("LAST", state["messages"][-1])
```

Shows in the uvicorn / debug terminal.

### Breakpoints (Cursor)

1. Red dot on a line (`agent_node`, `should_continue`, tool body)
2. Run **Debug FastAPI** (`F5`)
3. Hit `/chat` from Swagger
4. Step Over / Step Into

Best places to pause:

| File | Line idea | What you learn |
|---|---|---|
| `main.py` | before `ainvoke` | Incoming payload |
| `nodes.py` | after `ainvoke` | Did LLM request tools? |
| `graph.py` | inside `should_continue` | Routing decision |
| `order_tools.py` | after Mongo `to_list` | Real DB rows |

### Inspect tool calls without guessing

On the AI message:

```python
print(response.tool_calls)
```

---

## 15. Mental Model To Master This Stack

Memorize this loop:

```text
1. STATE carries truth (messages + user_id)
2. LLM PROPOSES actions (tool names) or answers
3. ROUTER chooses tools vs END
4. RUNTIME executes Python tools (ToolNode)
5. RESULTS append to messages
6. Repeat until LLM answers without tools
```

Map vocabulary:

| Concept | In this repo |
|---|---|
| Agent brain | `agent_node` + Gemini |
| Hands | `@tool` functions |
| Nervous system | LangGraph edges |
| Memory | `AgentState.messages` |
| Identity | `AgentState.user_id` |
| Knowledge (docs) | Vector store + `search_policy` |
| Knowledge (facts) | Mongo `orders` + order tools |
| Door to the world | FastAPI `/chat` |

If you can redraw the graph from memory and explain what `ToolNode` does, you understand agentic RAG.

---

## 16. What To Learn Next

When this feels solid, add one concept at a time:

1. **Conversation memory** — persist `messages` per session (Redis / Mongo checkpointer)
2. **Streaming** — token stream answers to the client
3. **Human-in-the-loop** — pause before cancel/refund actions
4. **Observability** — LangSmith / tracing to see each node
5. **Hybrid retrieval** — keyword + vector for policies
6. **Evaluation** — golden questions with expected tool calls
7. **Guardrails** — max tool iterations, allowlists, PII filters

---

## 17. Current Environment & Atlas Setup

Configured via `.env` (never commit secrets; `.env` is gitignored):

| Variable | Purpose | Current project value |
|---|---|---|
| `GEMINI_API_KEY` | Gemini auth | (secret in `.env`) |
| `GEMINI_LLM_MODEL` | Chat model | `gemini-3.1-flash-lite` |
| `GEMINI_EMBEDDING_MODEL` | Embeddings | `gemini-embedding-001` |
| `MONGODB_URI` | Atlas connection | `mongodb+srv://...@cluster0.weabrwi.mongodb.net/...` |
| `MONGODB_DATABASE` | DB name | `langchain_rag` |
| `REDIS_URL` | Reserved for later (sessions/cache) | `redis://localhost:6379` |

### Atlas collections used by this app

| Collection | Role |
|---|---|
| `orders` | Structured order rows (seed script) |
| `policy_chunks` | Embedded policy text + vectors |

### Vector search (must match code)

```text
Database:     langchain_rag
Collection:   policy_chunks
Index name:   policy_vector_index
Dimensions:   3072
Code file:    app/rag/vector_store.py
```

After changing `.env`, **restart** uvicorn / Debug FastAPI so settings reload.

---

## Quick Reference — Run The System

```bash
# 1. Activate venv
source .venv/bin/activate

# 2. Seed orders into Atlas (structured data)
python -m scripts.seed_orders

# 3. Ingest policies into Atlas policy_chunks (RAG)
#    Prefer once; re-running duplicates unless you clear first
python -m scripts.ingest_policies

# 4. (First time only) create Atlas vector index if missing:
#    vector_store.create_vector_search_index(dimensions=3072)
#    Index name used by app: policy_vector_index

# 5. Run API
uvicorn app.main:app --reload
# or Debug FastAPI via F5

# 6. Open docs
# http://127.0.0.1:8000/docs
```

Example chat bodies:

```json
{
  "user_id": "USER-001",
  "message": "What did I order today?"
}
```

```json
{
  "user_id": "USER-001",
  "message": "What is the refund policy?"
}
```

---

## One-Sentence Summary

**This is an AI Agent + RAG + LangGraph project: an LLM chooses tools inside a LangGraph loop; RAG is the policy tool backed by Atlas vector index `policy_vector_index`; orders come from MongoDB; `ToolNode` executes tools; state + `InjectedState(user_id)` keep the loop correct and secure.**

Read this doc once end-to-end, then re-read sections 7–9 with the code open beside you. That is the fastest path to mastering this architecture.
