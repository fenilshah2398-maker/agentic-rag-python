# Learn this project, file by file

Open this file in Cursor. Keep it on one side. Open each file I name on the other side. Read a section, look at the real code, then move on.

This is one app with two programs:

- **React** draws the screen in the browser (port `5173`)
- **FastAPI** does the real work on your computer (port `8000`)

The browser never talks to MongoDB, Redis, or Gemini. It only talks to FastAPI.

Use simple clicks, not memory:

| You want this | Open this URL |
|---|---|
| Sign in / sign up | http://localhost:5173/ |
| Chat | http://localhost:5173/chat |
| Python API docs | http://127.0.0.1:8000/docs |

---

## How to use this guide

1. Start at the top. Do not jump.
2. When I name a file, open it and skim it while you read.
3. After each big step, stop and say the flow out loud in one sentence.
4. You already know a bit of React and Python. I will still name each idea the first time it appears.

Words you will see a lot:

| Word | Meaning here |
|---|---|
| **Route** | A URL the app answers, like `/auth/signin` or `/chat` |
| **Token** | A random string that proves you signed in. Not your password. Not your user id. |
| **Session** | Redis remembering `this token belongs to USER-A1B2C3` for one day |
| **Agent** | The Gemini model plus Python tools, wired as a graph |
| **Tool** | A Python function the model can ask FastAPI to run |
| **RAG** | Search policy text by meaning, then let the model answer from those chunks |
| **WebSocket** | One long live wire. Unlike HTTP, it stays open so answers can come later. |
| **Cache** | Saved answers in Redis so the same question does not call Gemini again |
| **Trace** | Evidence for one question: tools, chunks, scores, time, tokens |
| **Eval** | A fixed list of questions with three scores you can re-run |
| **Hybrid search** | Vector meaning + keyword tokens, then merge the two lists |
| **Guardrail** | Python that can refuse a question or an answer. Not a prompt. |
| **Citation** | The file and section a fact came from, shown under the bubble |

---

## 1. What this app does

A signed-in user chats with a support agent.

- "What is the refund policy?" → search policy markdown in MongoDB Atlas
- "What did I order today?" → look up that user's rows in the `orders` collection
- "Can I cancel ORD-1002 and get a refund?" → both tools, then one answer

The last 5 answers per user are saved in Redis for 10 minutes. Ask the same question again and the reply is tagged **From cache**. A close paraphrase can hit the **semantic cache**. Review the new production path in **Part H** at the bottom of this file.

The chat page never sends `user_id`. The server reads it from the session token.

```
You type in React
    -> Vite on port 5173
    -> Vite forwards /api and /ws to FastAPI on port 8000
    -> FastAPI uses Redis, MongoDB, and Gemini
    -> FastAPI sends the result back
    -> React draws it
```

---

## 2. Folder map (open this once)

Do not memorize this. Come back when you get lost.

```
agentic-rag-python/
├── .env.example              secrets template (copy to .env)
├── requirements.txt          Python packages
├── app/                      FastAPI brain
│   ├── main.py               HTTP door + chat WebSocket
│   ├── config.py             reads .env
│   ├── auth/                 sign up, sign in, sign out
│   ├── chat/service.py       cache check, then the agent
│   ├── cache/                exact answers, semantic cache, memory
│   ├── guardrails/           input + output checks in Python
│   ├── eval/                 golden questions + scoring
│   ├── agent/                LangGraph: think, tools, answer
│   ├── tools/                Mongo orders + policy search
│   ├── rag/                  hybrid search, rewrite, rerank, chunks
│   ├── db/                   Mongo + Redis clients
│   ├── trace.py              one request's evidence
│   └── models/               request/response shapes
├── data/policies/            refund.md, return.md, ... (## sections)
├── scripts/                  ingest, seed, eval
├── evals/                    last_run.json (gitignored)
└── frontend/                 React screen
    ├── vite.config.js        forwards /api and /ws to FastAPI
    └── src/
        ├── main.jsx          starts React
        ├── App.jsx           picks the page from the URL
        ├── auth/             login box shared by both pages
        ├── pages/            AuthPage and ChatPage
        ├── chat/             WebSocket hook
        └── lib/api.js        one fetch() helper
```

Two extra docs already exist if you want more later:

- `MASTER_GUIDE.md` — deeper theory of RAG and LangGraph
- `REACT_GUIDE.md` — extra React notes

This file is the one to follow first.

---

## 3. Two programs, four stores

```
Browser (React)
   |
   |  HTTP  /auth/*     sign up, sign in, sign out
   |  WS    /ws/chat    questions and answers
   v
FastAPI
   |
   +-- Redis      sessions + last-5 answers
   +-- MongoDB    users, orders, policy chunks
   +-- Gemini     chat model + embeddings
```

| Store | What lives there |
|---|---|
| **sessionStorage** (browser tab) | `token` and `{ user_id, name, email }`. Refresh keeps it. Close the tab, it is gone. |
| **localStorage** (browser) | Chat bubbles under `chat:messages:<user_id>`. Survives refresh and sign-out. |
| **Redis** | `session:<token> -> user_id` (1 day). `chat:recent:<user_id>` list of last 5 answers (10 minutes). |
| **MongoDB Atlas** | `users`, `orders`, `policy_chunks` |
| **Gemini** | Thinks. Turns questions into tool calls. Turns policy text into vectors. |

---

## 4. Follow the flow

We start at the bottom (config and data), then we start the page, then we sign in, then we ask a question.

---

# Part A — Before the page even opens

These files load when Python starts. They do not draw anything.

---

## File: `.env.example`

Open: `.env.example`

This is the list of secrets the Python app needs. You copy it to `.env` and fill the values. `.env` is not in git.

| Key | Job |
|---|---|
| `GEMINI_API_KEY` | Talk to Google Gemini |
| `GEMINI_LLM_MODEL` | Which chat model thinks |
| `GEMINI_EMBEDDING_MODEL` | Which model turns text into vectors |
| `MONGODB_URI` | Atlas connection string (`mongodb+srv://...`) |
| `MONGODB_DATABASE` | Database name, usually `langchain_rag` |
| `REDIS_URL` | Usually `redis://localhost:6379` |

Never put secrets in Python files. Always read them from `.env`.

---

## File: `app/config.py`

Open: `app/config.py`

`pydantic-settings` reads `.env` and turns each key into a typed field.

```
GEMINI_API_KEY   ->  settings.gemini_api_key
MONGODB_URI      ->  settings.mongodb_uri
```

Every other Python file does:

```python
from app.config import settings
```

There is one `settings` object for the whole process. Change `.env`, then restart uvicorn so the new values load.

---

## File: `app/db/mongo.py`

Open: `app/db/mongo.py`

One Mongo client for the whole app. Connection pooling lives here.

Three collections:

| Collection | Who uses it | What is inside |
|---|---|---|
| `users` | `app/auth/routes.py` | One document per account: `user_id`, name, email, salt, hash |
| `orders` | `app/tools/order_tools.py` | Product, amount, status, date, `user_id` |
| `policy_chunks` | RAG path | Split policy text + embedding vectors |

`users_collection`, `orders_collection`, and `policy_collection` are just handles. Queries happen in other files.

---

## File: `app/db/redis.py`

Open: `app/db/redis.py`

Four lines. Creates one async Redis client from `REDIS_URL`.

Two other files import `redis_client`:

- `app/auth/sessions.py` — login tokens
- `app/cache/chat_cache.py` — last 5 answers

`decode_responses=True` means Redis gives you Python strings, not bytes.

---

## File: `requirements.txt`

Open: `requirements.txt`

Python packages, grouped by job:

- **Web:** `fastapi`, `uvicorn`
- **Settings:** `pydantic`, `pydantic-settings`
- **Stores:** `pymongo`, `redis`
- **Agent:** `langchain`, `langgraph`, `langchain-google-genai`, `langchain-mongodb`

You install once: `pip install -r requirements.txt`

---

# Part B — One-time setup (policies and demo orders)

You run these scripts once (or when you want fresh data). The chat page does not run them.

---

## Files: `data/policies/*.md`

Open any one: `data/policies/refund.md`

Four short markdown files: refund, return, delivery, cancellation.

These are the company rules. Gemini does not know them by heart. The ingest script cuts them into chunks, turns each chunk into a vector, and stores them in MongoDB. Later, `search_policy` finds the nearest chunks.

---

## File: `app/rag/ingestion.py`

Open: `app/rag/ingestion.py`

Offline helper. No network writes here.

1. `load_policy_documents()` reads every `*.md` in `data/policies/` into LangChain `Document` objects. `metadata.source` is the filename, like `refund.md`.
2. `split_documents()` cuts long text into chunks of about 500 characters, with 100 characters of overlap so a sentence at a cut is not lost.

Why chunk? Embeddings work better on a focused passage than on a whole file.

---

## File: `app/rag/embeddings.py`

Open: `app/rag/embeddings.py`

Turns text into a list of numbers (a vector). Same model for two moments:

- **Offline:** each policy chunk → vector → MongoDB
- **Online:** the tool query → vector → find nearest chunks

The model must be the same both times, or search is nonsense.

At the bottom there is a smoke check: it embeds `"What is the refund policy?"` when this file is first imported. That proves the API key works. It also means the first import costs one embedding call.

---

## File: `app/rag/vector_store.py`

Open: `app/rag/vector_store.py`

The Atlas vector store named `policy_chunks`, index name `policy_vector_index`.

`$vectorSearch` needs MongoDB Atlas, not a local `mongod`. The index dimension must match the embedding size (3072 for `gemini-embedding-001`).

Used by:

- `scripts/ingest_policies.py` → write chunks
- `app/rag/retriever.py` → search chunks

---

## File: `app/rag/retriever.py`

Open: `app/rag/retriever.py`

Thin wrapper: `vector_store.as_retriever(k=4)`.

When the policy tool runs, it asks this retriever for the 4 closest chunks. Tune `k` up for more context, down for shorter prompts.

---

## File: `scripts/ingest_policies.py`

Open: `scripts/ingest_policies.py`

Run from project root:

```
python -m scripts.ingest_policies
```

Flow:

```
data/policies/*.md
  -> load_policy_documents()
  -> split_documents()
  -> vector_store.aadd_documents()   # Gemini embed + write to Atlas
```

**Warning:** this **appends**. Run it twice without clearing `policy_chunks` and you get duplicates. Clear the collection first if you want a clean index.

---

## File: `scripts/seed_orders.py`

Open: `scripts/seed_orders.py`

Run from project root:

```
python -m scripts.seed_orders
```

Wipes `orders`, then inserts three demo rows for **`USER-8624C7`**:

| Order | When | Status | Shows in "today"? |
|---|---|---|---|
| ORD-1001 MacBook | 2 hours ago | DELIVERED | yes |
| ORD-1002 iPhone | 1 hour ago | SHIPPED | yes |
| ORD-1003 Headphones | yesterday | CANCELLED | no |

A brand-new sign-up gets a different `user_id`, like `USER-A1B2C3`. That account can still ask policy questions. Order questions return empty until orders exist for that id.

---

# Part C — The browser starts

Now we follow what happens when you open http://localhost:5173

---

## File: `frontend/index.html`

Open: `frontend/index.html`

Normal HTML shell. One empty box: `<div id="root"></div>`. One script: `/src/main.jsx`.

React will fill that box. You almost never edit this file.

---

## File: `frontend/src/main.jsx`

Open: `frontend/src/main.jsx`

This is the first JavaScript the browser runs.

Three wrappers around the screens. Order matters:

```
StrictMode          React extra checks in development
  BrowserRouter     watches the URL: / and /chat
    AuthProvider    holds who is logged in
      App           picks the page that matches the URL
```

`import "./styles.css"` loads the look of both pages.

On first paint, `AuthProvider` looks in `sessionStorage`. No token → you see the sign-in form. A saved token from this tab → you are already logged in.

---

## File: `frontend/src/App.jsx`

Open: `frontend/src/App.jsx`

App does not draw the form or the chat. It only maps URL → page.

| URL | What you see | File |
|---|---|---|
| `/` | Sign in / sign up | `pages/AuthPage.jsx` |
| `/chat` | Chat, but only if signed in | `pages/ChatPage.jsx` wrapped in `ProtectedRoute` |

`ProtectedRoute` is a gate. Empty `user` → bounce back to `/`.

---

## File: `frontend/vite.config.js`

Open: `frontend/vite.config.js`

Vite is the React dev server on port 5173. Two proxies hide FastAPI behind the same host, so the browser does not hit CORS for these calls:

```
Browser:  POST http://localhost:5173/api/auth/signin
Vite:     strips /api
FastAPI:  POST http://127.0.0.1:8000/auth/signin

Browser:  ws://localhost:5173/ws/chat
Vite:     keeps the socket
FastAPI:  ws://127.0.0.1:8000/ws/chat
```

That is why React code says `/api/auth/signin` and Python says `/auth/signin`. They are one step apart on purpose.

---

## File: `frontend/src/lib/api.js`

Open: `frontend/src/lib/api.js`

One helper for every HTTP call.

```js
api("/auth/signin", { method: "POST", body: { email, password } })
```

What it does:

1. Prefixes `/api` so Vite can forward it
2. `JSON.stringify` on the body (fetch wants a string)
3. If you pass `token`, sets `Authorization: Bearer <token>` (sign-out uses this)
4. On a failed response, throws FastAPI's `detail` string so the form can show it

The chat socket does **not** use this file. WebSocket cannot set that header, so the token rides in the first socket message instead.

---

## File: `frontend/src/auth/AuthContext.jsx`

Open: `frontend/src/auth/AuthContext.jsx`

Shared login box for the whole app.

`AuthProvider` in `main.jsx` wraps `<App />`. Any child can call `useAuth()` and get:

```
{ user, token, signIn, signUp, signOut }
```

State:

- `user` — `{ user_id, name, email }` or `null`
- `token` — the random session string or `null`

`remember(session)` writes both into `sessionStorage` and into React state.

| Action | HTTP | Then |
|---|---|---|
| `signUp` | `POST /auth/signup` | `remember()` |
| `signIn` | `POST /auth/signin` | `remember()` |
| `signOut` | clear browser first, then `POST /auth/signout` | Redis deletes the token |

`sessionStorage` lasts for this tab. Refresh keeps you signed in. Close the tab, next visit asks you to sign in again.

---

## File: `frontend/src/auth/ProtectedRoute.jsx`

Open: `frontend/src/auth/ProtectedRoute.jsx`

Eight lines. If `user` is empty, `<Navigate to="/" replace />`. `replace` means the blocked `/chat` visit does not stay in the back-button history.

If `user` exists, it renders `children`, which is `<ChatPage />`.

---

## File: `frontend/src/pages/AuthPage.jsx`

Open: `frontend/src/pages/AuthPage.jsx`

One screen, two modes: `"signin"` or `"signup"`. The name field only shows in signup.

The inputs are **controlled**: React state holds the text, the input's `value` is that state. Typing calls `setEmail`, React renders again, the box shows the new text.

If `user` is already set (including after a refresh), this page immediately sends you to `/chat`.

Submit:

1. `event.preventDefault()` so the browser does not reload
2. `busy` disables the button (no double click, no two accounts)
3. Call `signUp` or `signIn` from `AuthContext`
4. On success, `navigate("/chat")`
5. On error, show `err.message` (that is FastAPI's `detail`)

---

## File: `frontend/src/styles.css`

Open: `frontend/src/styles.css`

All look-and-feel for both pages. `App.css` and `index.css` are empty leftovers. The real classes (`auth-page`, `chat-page`, `bubble`, `status-ready`) live here.

You can skip this file until you want to change colors.

---

# Part D — Sign up / sign in on the server

You pressed **Create account** or **Sign in**. React called `api()`. Now Python.

---

## File: `app/main.py` (the HTTP door)

Open: `app/main.py`

This file is the door. Business logic lives elsewhere.

On startup (`lifespan`):

```python
await users_collection.create_index("email", unique=True)
```

One email can register only once. Mongo enforces that.

Then:

1. **CORS** — lets the React origin `http://localhost:5173` call port 8000
2. **Auth router** — mounts `/auth/signup`, `/auth/signin`, `/auth/signout`
3. **GET `/health`** — simple `{ "status": "ok" }`
4. **POST `/chat`** — Swagger / curl path. React does not use this. The chat page uses the WebSocket below.
5. **WebSocket `/ws/chat`** — the live chat wire (we come back to this in Part E)

CORS is for direct browser → 8000 calls. The Vite proxy already hides `/api` and `/ws` on 5173. CORS is still useful if you open `/docs` or call 8000 yourself.

---

## File: `app/auth/passwords.py`

Open: `app/auth/passwords.py`

Mongo never stores the real password.

`hash_password(password)`:

1. Makes a random `salt` (sign-up) or reuses the saved salt (sign-in)
2. Runs PBKDF2-HMAC-SHA256 120,000 times
3. Returns `(salt, hash)`

`verify_password` hashes the typed password with the saved salt and compares with `secrets.compare_digest` (constant-time, so timing does not leak "this password was almost right").

Two users with the same password get different hashes because each has a different salt.

---

## File: `app/auth/sessions.py`

Open: `app/auth/sessions.py`

A token is a random string. Redis remembers who it belongs to:

```
session:<token>  =  USER-A1B2C3    (expires in 1 day)
```

| Function | When |
|---|---|
| `create_session(user_id)` | End of sign-up and sign-in |
| `get_user_id(token)` | Chat socket first message |
| `delete_session(token)` | Sign-out |

The browser keeps the token. The server looks it up. The question message does not need a user id.

---

## File: `app/auth/routes.py`

Open: `app/auth/routes.py`

All paths here are prefixed with `/auth`.

### Sign up — `POST /auth/signup`

Body: `{ name, email, password }`

1. Trim name. Lowercase and trim email (`Fenil@Mail.com` and `fenil@mail.com` are the same account).
2. Server checks again: name ≥ 2, email looks valid, password ≥ 8. The React form checks too. The server must still check, because anyone can call this route without the form.
3. Hash the password. Build a user document with `user_id` like `USER-A1B2C3`.
4. Insert into Mongo. Duplicate email → 409 `"An account with this email already exists."`
5. `create_session` in Redis.
6. Return `{ token, user }`. `user` has id, name, email. **No salt. No hash.**

### Sign in — `POST /auth/signin`

Body: `{ email, password }`

1. Find the user by email.
2. Same error for "email missing" and "password wrong": `"Email or password is wrong."` So a caller cannot learn which emails are registered.
3. New Redis session. New token. Old tokens from earlier sign-ins stay valid until they expire or you sign out of that session.

### Sign out — `POST /auth/signout`

Header: `Authorization: Bearer <token>`

Deletes `session:<token>` in Redis. That token cannot open a chat socket anymore.

---

## Stop and say this out loud

```
AuthPage
  signIn() or signUp()
    -> api.js POST /api/auth/...
    -> Vite strips /api
    -> FastAPI /auth/signin or /signup
    -> Mongo users collection
    -> Redis session:<token> = user_id
    -> { token, user } back to React
    -> sessionStorage
    -> URL becomes /chat
```

---

# Part E — The chat page and the socket

You are signed in. The URL is `/chat`.

---

## File: `frontend/src/pages/ChatPage.jsx`

Open: `frontend/src/pages/ChatPage.jsx`

This file is the screen. The socket logic is in the hook.

```
useAuth()        -> user, token, signOut
useChatSocket()  -> messages, status, sendMessage
draft            -> text currently in the input box
```

Header: your name, email, a status pill (`connecting` / `ready` / `thinking` / `disconnected`), Sign out.

Middle: bubbles. Empty state says "Ask about a refund...". A cached answer shows a **From cache** tag.

Bottom: input + Send. Send is disabled until the socket is `ready` and the box has text. While `thinking`, a second send is ignored.

Sign out: `signOut()` then `navigate("/")`.

---

## File: `frontend/src/chat/useChatSocket.js`

Open: `frontend/src/chat/useChatSocket.js`

Custom hook. ChatPage calls it and gets `{ messages, status, sendMessage }`.

Two kinds of storage:

| Place | What | Why |
|---|---|---|
| `localStorage` key `chat:messages:<user_id>` | Bubble list | Refresh still shows the conversation |
| `useRef` | The live `WebSocket` object | The screen does not draw the socket, so it is not React state |

On first render it reads old bubbles from `localStorage`. Then a `useEffect` opens:

```
ws://localhost:5173/ws/chat
```

As soon as it opens, it sends:

```json
{ "type": "auth", "token": "..." }
```

The browser WebSocket API cannot set an `Authorization` header. That is why the token is the first message.

When a message arrives:

| Server `type` | What React does |
|---|---|
| `ready` | status = `ready`, you can type |
| `status` | status = `"thinking"` |
| `error` | show that text in the status pill |
| `answer` | add an assistant bubble, status back to `ready` |

`sendMessage`:

1. Add your bubble immediately (feels instant)
2. Set status to `thinking`
3. Send `{ "type": "question", "message": "..." }` — **no user_id**

Every time `messages` changes, another `useEffect` writes the list to `localStorage`. Another account on this browser has a different `user_id`, so they do not see your transcript.

When you leave `/chat`, the effect cleanup closes the socket.

---

## File: `app/main.py` (the WebSocket)

Go back to `app/main.py`, function `ws_chat`.

One long connection per open chat page.

```
1. Browser sends   { "type": "auth", "token": "..." }
2. Server looks up token in Redis
3. Server replies  { "type": "ready" }
4. Browser sends   { "type": "question", "message": "..." }
5. Server sends    { "type": "status", "text": "thinking" }
6. Server sends    { "type": "answer", "answer": "...", "cached": false }
```

Rules in code:

- First message must be `auth`. Anything else → close.
- Bad or expired token → `{ type: "error", text: "Sign in again." }` then close.
- Until `user_id` is set, questions are not accepted.
- Empty question → error, connection stays open.
- `user_id` came from the token. A `user_id` inside the question is ignored on purpose.

Then it calls `answer_question(user_id, message)` from the chat service.

---

## File: `app/chat/service.py`

Open: `app/chat/service.py`

Same path as `POST /chat`. One function: `answer_question(user_id, message)`.

```
1. Hash user + cleaned question
2. Look in Redis last-5 list
3. Hit  -> return { answer, cached: True }     Gemini does not run
4. Miss -> run the LangGraph agent
         -> save the answer in Redis
         -> return { answer, cached: False }
```

`as_text` exists because Gemini sometimes returns a string, sometimes a list of text blocks. The cache and the socket always get a plain string.

---

## File: `app/cache/chat_cache.py`

Open: `app/cache/chat_cache.py`

Last 5 answers, one Redis list per user.

```
chat:recent:USER-A1B2C3  =  [ newest, ..., oldest ]   max 5, TTL 10 minutes
```

`normalize` lowercases and squeezes spaces, so these two questions share a hash:

```
"  What is the Refund Policy?  "
"what is the refund policy?"
```

`question_hash` fingerprints `user_id|cleaned question`. Same sentence, different user → different hash. You never get another person's answer.

Save path:

1. `LPUSH` the new item at the front
2. `LTRIM` keep indexes 0..4
3. `EXPIRE` restart the 10-minute timer

Why 10 minutes? "What did I order today?" should not stay correct-looking after the orders change.

---

## File: `app/models/request.py`

Open: `app/models/request.py`

Pydantic body for `POST /chat`: `{ user_id, message }`.

React does not use this. Swagger at `/docs` does. FastAPI validates the JSON before the agent runs.

---

## File: `app/models/response.py`

Open: `app/models/response.py`

Documents the intended reply shape `{ answer, sources }`. The live code currently returns a plain dict. `sources` is not wired yet. Safe to skip.

---

## Stop and say this out loud

```
ChatPage
  useChatSocket()
    -> localStorage restores old bubbles
    -> WebSocket opens
    -> { type: "auth", token }
    -> Redis returns user_id
    -> { type: "ready" }

Send
  -> your bubble on screen
  -> { type: "question", message }
  -> hash(user_id + question)
  -> Redis last-5
       hit:  saved answer, cached true
       miss: agent (next part)
  -> { type: "answer" }
  -> assistant bubble
  -> localStorage updated
```

---

# Part F — Cache miss: the agent thinks

Redis did not have this question. Now Gemini and the tools run.

Mental model: the model does **not** know your orders or policies. It **chooses a tool**. Python **runs** the tool. The model reads the result and writes the answer.

```
START
  -> agent (THINK: Gemini)
       |
       +-- has tool_calls?  --yes--> tools (DO: Python) --> agent again
       |
       no
       v
      END
```

---

## File: `app/agent/state.py`

Open: `app/agent/state.py`

The backpack that travels through every graph node.

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # conversation so far
    user_id: str                             # trusted, from the token
```

`add_messages` is important. Without it, returning `{ "messages": [new] }` would **replace** the whole list and the tool loop would forget the question. With it, new messages **append**.

`user_id` is not chosen by Gemini. It is injected into order tools later.

---

## File: `app/rag/llm.py`

Open: `app/rag/llm.py`

The Gemini chat model. `temperature=0` means less invention, better for facts.

This object cannot call tools yet. `nodes.py` does `llm.bind_tools(tools)` so Gemini can emit structured `tool_calls` instead of "please call get_today_orders".

---

## File: `app/agent/nodes.py`

Open: `app/agent/nodes.py`

The THINK step. This file does **not** run tools. It only asks Gemini what to do.

It collects three tools:

- `get_today_orders`
- `get_order_by_id`
- `search_policy`

Then binds them onto the model, and prepends a **system prompt** every turn:

- Use Mongo tools for orders
- Use policy search for company rules
- Never invent orders or policy
- If evidence is thin, say so

`agent_node(state)`:

1. Prepend the system rules to the conversation
2. `await llm_with_tools.ainvoke(...)`
3. Return `{ "messages": [response] }` which **appends**

The response is either:

- plain text → graph ends
- `tool_calls` → graph goes to the tools node

---

## File: `app/agent/graph.py`

Open: `app/agent/graph.py`

The wiring. No Gemini calls here. It only says who talks to whom.

- Node `"agent"` = `agent_node`
- Node `"tools"` = LangGraph `ToolNode(tools)` — this is what actually runs Python
- `START` always goes to `"agent"`
- After agent, `should_continue` looks at the last message:
  - has `tool_calls` → `"tools"`
  - else → `END`
- After tools, **always** back to `"agent"` so the model can call more tools or write the final answer

`graph = graph_builder.compile()` is the runnable object. `answer_question` calls `graph.ainvoke({ messages, user_id })`.

---

## File: `app/tools/order_tools.py`

Open: `app/tools/order_tools.py`

Hands for order facts. Not RAG. Exact Mongo filters.

**Security:** `user_id` is `InjectedState("user_id")`. The model does not see that argument. `ToolNode` fills it from graph state. The model cannot invent `USER-999` and read someone else's orders.

### `get_today_orders`

Finds this user's orders from UTC midnight until now. Yesterday's ORD-1003 is excluded on purpose.

### `get_order_by_id(order_id)`

The model may supply `order_id` from the user's words ("ORD-1002"). Both `user_id` **and** `order_id` must match. Guessing another person's order id still returns `"Order not found"`.

`_id` is stripped because Mongo ObjectId is ugly for the model.

---

## File: `app/tools/policy_tools.py`

Open: `app/tools/policy_tools.py`

The RAG tool inside the agent.

```
LLM calls search_policy(query="refund processing time")
  -> retriever embeds the query
  -> Atlas $vectorSearch finds nearest chunks
  -> return [{ content, source: "refund.md" }, ...]
```

Orders = exact filters (structured). Policies = closest meaning (unstructured).

The model chooses the query. Short topical queries work better than dumping the whole user sentence.

---

## One real question, all the way through

You type: **"What is the refund policy?"**

```
ChatPage onSubmit
  -> useChatSocket.sendMessage
  -> bubble appears
  -> socket { type: "question", message: "What is the refund policy?" }

app/main.py ws_chat
  -> user_id already known from the token
  -> { type: "status", text: "thinking" }
  -> answer_question(user_id, message)

chat_cache
  -> hash(user_id + "what is the refund policy?")
  -> not in last 5

graph.ainvoke
  START -> agent_node
    Gemini sees tools + system rules
    Gemini emits tool_calls: search_policy("refund policy")
  should_continue -> "tools"
  ToolNode runs search_policy
    retriever -> 4 chunks from refund.md / cancellation.md
    ToolMessage appended
  back to agent_node
    Gemini reads the chunks
    Gemini writes a short answer, no more tool_calls
  should_continue -> END

save_answer in Redis
socket { type: "answer", cached: false }
React adds assistant bubble
localStorage writes the list
```

Ask the same thing again within 10 minutes:

```
hash matches Redis list
  -> { type: "answer", cached: true }
  -> bubble with "From cache"
  -> Gemini does not run
```

A mixed question: **"Can I cancel ORD-1002 and get a refund?"**

Gemini may call `get_order_by_id("ORD-1002")` **and** `search_policy("cancellation refund")`, then combine: the iPhone is SHIPPED, so cancellation is normally not allowed.

---

# Part G — Sign out, refresh, leftover files

---

## Sign out

1. React clears `user` and `token` from memory and `sessionStorage`
2. `POST /api/auth/signout` with `Authorization: Bearer <token>`
3. FastAPI deletes `session:<token>` in Redis
4. Page goes to `/`

The chat transcript stays in `localStorage` under your `user_id`. Sign in again on this browser, those bubbles come back. Another person on this browser has a different id, so they do not see yours.

---

## Refresh the tab

`sessionStorage` still has token + user → AuthPage sends you to `/chat` → `useChatSocket` reads bubbles from `localStorage` first, then opens a new socket and authenticates again.

Close the tab → `sessionStorage` is gone → next visit is the sign-in form. `localStorage` bubbles are still there for the next sign-in of that user.

---

## Leftover / skip files

| File | Why you can skip it |
|---|---|
| `frontend/src/App.css` | Empty |
| `frontend/src/index.css` | Empty |
| `frontend/eslint.config.js` | Lint rules only |
| `frontend/package.json` | Scripts: `npm run dev`, `npm run build` |
| `frontend/README.md` | Default Vite text |
| `.vscode/launch.json` | Cursor/VS Code debugger for uvicorn |
| `MASTER_GUIDE.md` | Extra theory after this file |
| `REACT_GUIDE.md` | Extra React notes after this file |

---

# Cheat sheet

## Where each kind of data lives

```
Browser sessionStorage     token + { user_id, name, email }
Browser localStorage       chat bubbles per user_id
Redis session:<token>      user_id (1 day)
Redis chat:recent:<user>   last 5 answers (10 minutes)
Mongo users                salt + password hash
Mongo orders               product rows keyed by user_id
Mongo policy_chunks        embedded policy text
Gemini                     thinking + embeddings, no long-term store here
```

## Who talks to whom

```
AuthPage  --HTTP-->  api.js  --Vite-->  auth/routes.py  --> mongo users
                                                    \--> redis sessions

ChatPage  --WS---->  useChatSocket  --Vite-->  main.py ws_chat
                                              --> chat/service.py
                                              --> chat_cache.py (Redis)
                                              --> agent graph
                                                    --> order_tools (Mongo)
                                                    --> policy_tools (vector search)
                                                    --> Gemini
```

## Suggested reading order if you only have 30 minutes

1. `frontend/src/main.jsx` + `App.jsx`
2. `frontend/src/auth/AuthContext.jsx` + `app/auth/routes.py`
3. `frontend/src/chat/useChatSocket.js` + `app/main.py` (`ws_chat`)
4. `app/chat/service.py` + `app/cache/chat_cache.py`
5. `app/agent/graph.py` + `app/agent/nodes.py`
6. `app/tools/order_tools.py` + `app/tools/policy_tools.py`

That is the whole loop: screen → login → socket → cache → agent → tools → answer.

---

# How to run it (short)

Python 3.11+, Node 20+, Redis running, MongoDB Atlas, `.env` filled.

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m scripts.ingest_policies
python -m scripts.seed_orders
```

Terminal 1, project root:

```
uvicorn app.main:app --reload
```

Terminal 2:

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173  
Sign up. Ask: `What is the refund policy?`  
Ask it again. The reply should say **From cache**.

Then keep reading **Part H** below. That is the rest of the RAG path.

```
python -m scripts.eval_rag --self-test
python -m scripts.eval_rag --limit 3
python -m scripts.ingest_policies --dry-run
```

Ask in chat:

- `What is the refund window?` — trace + citation chip `refund.md · Refund window`
- `What's your refund policy?` — may say **From semantic cache**
- `And for returns?` — memory uses the last turn
- `What is the weather?` — input guardrail refuses
- `Please cancel ORD-1004` — Approve / Reject (seed that order first)

---

# Part H — Production RAG, one idea at a time

Parts A–G get a signed-in user to an answer. This part is what a senior engineer adds next so the answer is **measurable, grounded, and safe**.

Do not jump. Open the file I name. After each step, say the flow out loud in one sentence.

The 12 steps, in the order we built them:

1. Traces
2. Golden eval
3. Heading chunks + metadata
4. Hybrid search
5. Query rewrite
6. Rerank, then abstain
7. Citations
8. Guardrails
9. Conversation memory
10. Human approval before a write
11. Document lifecycle
12. Semantic cache + latency budget

---

## H1. Traces — see why, not only what

Open: `app/trace.py`  
Also: `app/chat/service.py`, `frontend/src/chat/TracePanel.jsx`

A wrong answer has three common causes:

1. The model picked the wrong **tool**
2. Search returned the wrong **chunks**
3. The model **worded** the answer badly from good chunks

`answer_question` used to return only the final sentence. You could not tell which of those three happened.

Now every question opens a `RequestTrace`. Think of it as a pocket for this one request. The retriever and the agent write into it. Two users chatting at once each get their own pocket (a contextvar).

What lands in the pocket:

| Field | Meaning |
|---|---|
| `question` | What you typed |
| `original_query` / `search_query` | What was embedded (step 5) |
| `tools` | Names the model asked to run |
| `vector_hits` / `keyword_hits` | The two lists before merge (step 4) |
| `chunks` | The 4 that reached the prompt, with scores |
| `latency_ms` | rewrite / retrieve / rerank / llm / total |
| `tokens` | Gemini in / out |
| `abstain` | Search said "not good enough" |

The **full** block prints in the FastAPI terminal (`RAG TRACE`). A **short** copy goes to the chat bubble and to Redis.

Ask: `What is the refund window?`  
You should see four rows and scores. If you do not, restart FastAPI so it loads `trace.py`.

One sentence: **a trace is the evidence for one question.**

---

## H2. Golden eval — do not tune by feeling

Open: `app/eval/cases.py`  
Then: `app/eval/scoring.py`  
Then: `scripts/eval_rag.py`

A trace tells you what happened **once**. An eval tells you if a change helped **twenty times**.

Each case names:

- `expected_tools` — the agent must call these (extras are OK)
- `expected_sources` — at least one of these files must appear in the chunks
- `expected_sections` — at least one heading name, e.g. `Refund window`
- `must_contain` — a fact copied from the markdown, like `5-7`

Three independent scores:

| Score | Question it answers |
|---|---|
| **Tool choice** | Did it look in the right place? |
| **Retrieval** | Did the right file / section come back? |
| **Answer fact** | Did the sentence keep a known string? |

`"5-7"` and `"5 to 7"` count as the same fact.

Evals call `run_agent()`, not the Redis cache. A leftover chat answer cannot fake a pass.

```
python -m scripts.eval_rag --self-test    # fake traces, no Gemini
python -m scripts.eval_rag --limit 3      # first three live cases
python -m scripts.eval_rag                # all 20 (slow, calls Gemini)
```

Order cases belong to `USER-8624C7`. Run `python -m scripts.seed_orders` first.

The table prints at the end. `evals/last_run.json` is written so you can compare two runs. That file is gitignored.

One sentence: **after every later change, re-run the eval and look at the three percentages.**

---

## H3. Heading chunks — retrieval starts at ingest

Open: `data/policies/refund.md`  
Then: `app/rag/ingestion.py`  
Then: `scripts/ingest_policies.py`

The old splitter cut every file at 500 characters. These policies were short, so each file became **one blob**. "Refund window" and "promotional discounts" lived in the same vector.

Now each `##` heading is its own chunk, with three tags:

| Tag | Example |
|---|---|
| `source` | `refund.md` |
| `policy` | `refund` |
| `section` | `Refund window` |

The facts the eval looks for did not change. Only the **shape** of the files changed.

```
python -m scripts.ingest_policies --dry-run
```

You should see a line like:

`source=refund.md  policy=refund  section=Refund window`

That is the "done" check for this step. Then the real ingest writes to Atlas. Unchanged files are skipped (see H11).

One sentence: **one idea per chunk, and the heading becomes metadata.**

---

## H4. Hybrid search — meaning plus exact words

Open: `app/rag/bm25.py`  
Then: `app/rag/hybrid.py`

Vector search is good at meaning: "send the shoes back" ≈ return.  
It is weak at exact tokens: `5-7`, a heading name, a code.

So we run **two** lists:

1. **Vector** — Atlas `$vectorSearch`, top 20
2. **Keyword** — BM25 over the active chunks in Mongo, top 20

Then **Reciprocal Rank Fusion**. It does not mix raw scores (they live on different scales). It only uses rank:

```
fused(d) = 1/(60 + rank_on_vector) + 1/(60 + rank_on_keyword)
```

A chunk that is #1 on both lists beats a chunk that is #1 on only one.

The trace shows `vector_hits` and `keyword_hits` **before** the merge. That is how you debug hybrid. If the keyword list has `Refund window` and the vector list does not, fusion still has a chance to keep it.

We run BM25 in Python because the set is small. A bigger app would use Atlas Search. The fusion math stays the same.

One sentence: **two ranked lists, then one fused list.**

---

## H5. Query rewrite — embed a search string, not the essay

Open: `app/rag/rewrite.py`

The question you **answer** and the query you **embed** are not the same.

```
"can I send the shoes back if they don't fit?"
        →  "return policy time limit"
```

If the tool query is already short (6 words or fewer, a `?` at the end does not count), we skip Gemini and keep it. That saves a slow call when the model already wrote `refund window`.

The trace has two strings:

- `original_query` — what the tool received
- `search_query` — what was actually embedded

One sentence: **search the rewritten query; answer the original question.**

---

## H6. Rerank, then abstain — recall is not precision

Open: `app/rag/rerank.py`  
Then: `app/rag/retriever.py`

Hybrid pulls about **20** chunks. That is **recall**: do not miss the right one.

Rerank keeps the best **4**. That is **precision**: do not stuff the prompt with noise.

If the best **vector** score is under `0.78` **and** keyword search is also weak, we **abstain**. A weak match is not "close enough". A strong keyword hit (like `5-7`) can still support an answer — useful in the minute after ingest, when Atlas sometimes has no vectors yet. The tool returns:

```
{ "abstain": true, "reason": "no supporting policy", "chunks": [] }
```

The output guardrail (H8) then forces: `I don't have that in the policy.`

The whole online path is now one function, `search_policy_chunks`:

```
query → rewrite → hybrid → rerank / abstain → trace
```

`policy_tools.py` only calls that function. It does not know about BM25.

Ask something off-topic that slipped past the input guardrail, or a policy question with no matching section. The trace should say `abstain: True`. The bubble should not quote a random policy.

One sentence: **fetch wide, keep four, or say you do not know.**

---

## H7. Citations — name the file and the section

Open: `app/agent/nodes.py` (rule 10)  
Then: `app/guardrails/output.py` (`citations_from_chunks`)  
Then: `frontend/src/pages/ChatPage.jsx`

The model is told to write `(refund.md · Refund window)` after a policy fact.

The server also builds chips from the **chunks that actually reached the prompt**. The page does not parse the sentence. It trusts the retriever.

Under the bubble you should see a green chip:

`refund.md · Refund window`

That is grounded generation: the source is data, not a guess.

One sentence: **every policy fact should point at a file and a heading.**

---

## H8. Guardrails — code, not a wish in the prompt

Open: `app/guardrails/input.py`  
Then: `app/guardrails/output.py`  
Then: `app/agent/graph.py`

The system prompt already says "never invent policy". That is a **request**. A guardrail is a **lock**.

Three locks:

**Input** (before Gemini):

- Strip emails and long digit runs
- Block "ignore previous instructions" / "reveal the system prompt"
- Block questions that are not about orders or policy

Ask: `What is the weather?`  
You get a refusal. The graph does not run.

**Tools** (inside the graph):

- Only names in the allowlist may run
- After **4** think/tool rounds, `should_continue` goes to `END`
- `recursion_limit=12` is a second cap

**Output** (after Gemini):

- If search abstained → replace the answer with `I don't have that in the policy.`
- If we have chunks but the answer shares almost no words with them → same replacement

One sentence: **the prompt asks; Python enforces.**

---

## H9. Conversation memory — "and for returns?"

Open: `app/cache/memory.py`  
Then: `app/chat/service.py` (`load_history` / `append_turn`)

Each question used to start a **new** graph with only that one sentence. "And for returns?" had no link to the refund answer above it.

Redis now keeps the last **6** spoken turns per user (`chat:memory:<user_id>`). Only user text and assistant text. Not tool JSON.

`run_agent` prepends those turns, then the new question. The model can see the last exchange.

Ask: `What is the refund window?`  
Then: `And for returns?`  
The second answer should be about the **return** window (7 days), not a blank stare.

This is **not** the same as the bubble list in `localStorage`. That list is only for drawing the screen. The server memory is what the model sees.

One sentence: **the last few spoken turns travel with the new question.**

---

## H10. Human approval — the model cannot write orders

Open: `app/tools/order_tools.py` (`request_cancellation`)  
Then: `app/chat/approvals.py`  
Then: `app/main.py` (the `approval_response` branch)  
Then: `frontend/src/pages/ChatPage.jsx`

A write is different from a search. Search is safe to run. Changing `orders.status` is not.

```
You: Please cancel ORD-1004
  → model calls request_cancellation("ORD-1004")
  → tool looks up the row (still your user_id, injected)
  → tool returns needs_approval: true
  → it does NOT update Mongo
  → socket sends { type: "approval", order_id, product, status }
  → yellow card with Approve / Reject
```

Approve:

```
{ type: "approval_response", approved: true, order_id: "ORD-1004" }
  → execute_cancellation(user_id, "ORD-1004")
  → status becomes CANCELLED
```

Reject: nothing is written.

`ORD-1002` is SHIPPED. Even if you approve, execute refuses. Policy still wins.

`ORD-1004` is `PLACED` (added in `scripts/seed_orders.py`) so the happy path works. Re-seed if that row is missing:

```
python -m scripts.seed_orders
```

Those demo rows belong to `USER-8624C7`. A brand-new sign-up has a different id, so cancel will say "Order not found" until that user has a `PLACED` row.

One sentence: **the tool proposes; a human (or a later job) writes.**

---

## H11. Document lifecycle — do not pile up old chunks

Open: `app/rag/lifecycle.py`  
Then: `scripts/ingest_policies.py` again

The first ingest script **appended**. Run it twice and traces showed twin chunks with the same score.

Now each file has a **hash** and a **version**.

```
same hash as last time  → skip (no new Gemini embeddings)
hash changed            → version += 1
                        → delete that file's old chunks
                        → write new chunks with active=True
```

`--dry-run` still only prints. The real command talks to Atlas.

Unchanged policies cost **zero** embedding calls. That is the point.

One sentence: **a file that did not change is not re-embedded, and old chunks are removed when it did.**

---

## H12. Semantic cache + latency budget

Open: `app/cache/semantic.py`  
Then: `app/cache/chat_cache.py`  
Then: `app/trace.py` (`LATENCY_BUDGET_MS`)

Two caches, two jobs:

| Cache | Key | Hits when |
|---|---|---|
| Exact | hash(user + cleaned question) | The letters match |
| Semantic | cosine(embedding, stored embeddings) ≥ 0.93 | The **meaning** matches |

`"What is the refund policy?"` then `"What's your refund policy?"` can hit semantic cache. The bubble says **From semantic cache**.

We only do this for **policy** questions. Order answers go stale when a row changes. If the question has `ORD-1002`, we skip semantic cache.

Latency is recorded per stage. If a stage is slower than the budget, the trace lists it in `over_budget`. The first Gemini call on a cold model often blows the `llm` budget. That is useful, not a crash.

One sentence: **same letters → exact cache; same meaning → semantic cache; every stage has a time budget.**

---

## The full path, said slowly

You type: **"I want to send the shoes back. How long do I have?"**

```
ChatPage
  -> socket { type: "question", message: "..." }

input guardrail
  -> has "back" / return language → ok
  -> no injection, secrets stripped

exact cache  → miss
semantic cache → maybe miss (first time)

load last 6 turns from Redis
run_agent
  START → agent
    Gemini calls search_policy("return time limit shoes")
  tools
    rewrite  → "return policy time limit"   (if the query was long)
    vector top 20
    BM25 top 20
    RRF merge
    rerank → 4 chunks
    best vector 0.86 → keep
    trace records both lists
  agent again
    writes the 7-day fact + (return.md · Return window)
  END

output guardrail
  → answer shares words with the chunk → keep it
citations
  → chip: return.md · Return window
save memory, exact cache, semantic cache
socket { type: "answer", sources, trace }
```

Ask the same idea with different words a minute later: semantic cache, no Gemini.

Ask `What is the weather?`: input guardrail, no search.

Ask `Please cancel ORD-1004`: approval card, Mongo changes only after Approve.

---

## Part H cheat sheet

```
app/trace.py                 evidence pocket
app/eval/cases.py            20 golden questions
app/eval/scoring.py          three scores
scripts/eval_rag.py          run the eval
app/rag/ingestion.py         split on ##
app/rag/lifecycle.py         hash + version + replace
app/rag/rewrite.py           long sentence → short query
app/rag/bm25.py              keyword scores
app/rag/hybrid.py            vector + keyword + RRF
app/rag/rerank.py            top 4 or abstain
app/rag/retriever.py         the online path in one place
app/guardrails/input.py      refuse before Gemini
app/guardrails/output.py     refuse after Gemini
app/agent/graph.py           allowlist + max 4 tool rounds
app/cache/memory.py          last 6 spoken turns
app/cache/semantic.py        meaning cache
app/chat/approvals.py        propose vs write
app/tools/order_tools.py     request_cancellation
```

Suggested 20-minute pass on Part H:

1. `app/trace.py` + one chat question
2. `scripts/eval_rag.py --self-test`
3. `app/rag/retriever.py` (the new online path)
4. `app/guardrails/input.py` + "What is the weather?"
5. Approve flow on `ORD-1004`

