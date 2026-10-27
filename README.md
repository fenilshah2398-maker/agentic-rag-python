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

## Flow, step by step

Two programs are running. React is the screen in the browser. FastAPI is the brain on your computer. The browser never talks to MongoDB, Redis, or Gemini by itself. It only talks to FastAPI.

```
You type in React
    -> Vite on port 5173 receives it
    -> Vite forwards /api and /ws to FastAPI on port 8000
    -> FastAPI uses Redis, MongoDB, and Gemini
    -> FastAPI sends the result back
    -> React draws it
```

`/api/auth/signin` in the browser becomes `/auth/signin` on FastAPI. The Vite config strips the `/api` prefix. That is why the React code and the Python routes look one step apart.

### 1. The React app opens

`frontend/src/main.jsx` starts the page. Three wrappers sit around the screens:

1. `BrowserRouter` watches the URL. `/` is the sign-in page. `/chat` is the chat page.
2. `AuthProvider` holds who is logged in, so both pages can read it.
3. `App` picks the page that matches the URL.

On the first paint, `AuthContext` looks in `sessionStorage`.

- No saved token: `user` is empty, so you see the sign-in form.
- A saved token from this tab: `user` is filled, and the sign-in page sends you to `/chat`.

`sessionStorage` survives a refresh of this tab. Closing the tab clears it, so the next visit asks you to sign in again.

### 2. Sign up

You fill name, email, and password and press Create account.

1. `AuthPage` calls `signUp` from `AuthContext`.
2. `signUp` calls `api()`, which sends `POST /api/auth/signup` with the form JSON.
3. FastAPI checks the name, email, and password length.
4. The password is turned into a hash plus a random salt. The real password is not stored.
5. MongoDB saves one user document: `user_id`, name, email, salt, hash. The `user_id` looks like `USER-A1B2C3`.
6. Redis stores `session:<random token>` = that `user_id` for one day.
7. FastAPI returns `{ token, user }`. The user object has id, name, and email. It does not include the hash.
8. React saves `token` and `user` in `sessionStorage`, then moves the URL to `/chat`.

If the email is already registered, FastAPI returns an error and the form shows that message. The button stays disabled while the request is running so a double click does not create two accounts.

### 3. Sign in

Same path, with a smaller body: email and password only.

1. `POST /api/auth/signin`.
2. FastAPI finds the user by email in MongoDB.
3. It hashes the password you typed with the saved salt and compares it to the saved hash.
4. A match creates a new Redis session and returns a new token.
5. A mismatch returns "Email or password is wrong." The form shows that text.

Each sign-in makes a new token. The old token also stays valid until it expires or you sign out of that session.

### 4. What the token is for

The token is a random string. It is not your user id and it is not your password.

```
Browser stores:  token  +  { name, email, user_id }
Redis stores:    session:<token>  ->  USER-A1B2C3
```

Later requests prove who you are by sending the token. The server looks it up in Redis and gets the `user_id`. The chat page does not send `user_id` in the question.

### 5. The chat page opens

`ProtectedRoute` runs first. If `user` is empty, it sends you back to `/`. If you are signed in, `ChatPage` renders.

`useChatSocket` does three things:

1. It reads this user's old bubbles from `localStorage` under the key `chat:messages:<user_id>`. That is why a refresh still shows the conversation.
2. It opens one WebSocket to `/ws/chat`. The connection stays open.
3. As soon as the socket opens, it sends `{ "type": "auth", "token": "..." }`.

FastAPI checks that token in Redis.

- Token found: server remembers `user_id` for this connection and sends `{ "type": "ready" }`. The status pill says `ready`.
- Token missing or expired: server sends an error and closes the socket.

The browser WebSocket cannot set an `Authorization` header, so the token rides in that first message. Sign-out still uses the header, because sign-out is a normal HTTP call.

### 6. You ask a question

1. The Send button calls `sendMessage`.
2. React adds your bubble immediately and sets the status to `thinking`.
3. The socket sends `{ "type": "question", "message": "What is the refund policy?" }`.
4. FastAPI ignores any user id inside that message. It uses the `user_id` it stored when the socket authenticated.
5. `answer_question` builds a hash of `user_id + cleaned question`.
6. Redis list `chat:recent:<user_id>` is checked. It holds at most 5 saved answers.

Cache hit:

```
Redis has this hash
    -> return the saved answer
    -> Gemini does not run
    -> socket sends { type: "answer", answer: "...", cached: true }
    -> React adds the assistant bubble and the "From cache" tag
```

Cache miss:

```
Redis does not have this hash
    -> LangGraph agent runs
    -> the model may call the order tool (MongoDB) or the policy tool (vector search)
    -> the model writes the final answer
    -> that answer is pushed to the front of the Redis list
    -> the list is trimmed to 5
    -> socket sends { type: "answer", cached: false }
```

Every time the message list changes, React writes it to `localStorage`. The next refresh reads that list before the socket connects, then the socket connects again in the background.

Order questions only find rows whose `user_id` matches the signed-in user. The seed script inserts orders for `USER-8624C7`. A brand-new account has a different id, so that account sees policy answers and an empty order list until orders exist for it.

### 7. Sign out

1. React clears `user` and `token` from memory and from `sessionStorage`.
2. It sends `POST /api/auth/signout` with `Authorization: Bearer <token>`.
3. FastAPI deletes `session:<token>` in Redis. That token cannot open a socket anymore.
4. The page goes back to `/`.

The chat transcript stays in `localStorage` under your `user_id`. Signing in again on this browser shows those bubbles. Another person on this browser has a different `user_id`, so they do not see your transcript.

### 8. Picture of one question

```
AuthPage
  signIn()
    -> POST /auth/signin
    -> MongoDB checks the password hash
    -> Redis saves session token
    -> sessionStorage saves token + user
    -> URL becomes /chat

ChatPage
  useChatSocket()
    -> localStorage restores old bubbles
    -> WebSocket opens
    -> { type: "auth", token }
    -> Redis returns user_id
    -> { type: "ready" }

Send
  -> bubble appears on screen
  -> { type: "question", message }
  -> hash(user_id + question)
  -> Redis last-5 list
       hit:  saved answer, cached true
       miss: LangGraph -> MongoDB or policy search -> Gemini
             save answer in Redis
  -> { type: "answer" }
  -> assistant bubble
  -> localStorage updated
```