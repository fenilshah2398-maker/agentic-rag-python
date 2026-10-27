# React Guide — Sign-in, Chat, and the Socket

> Read this the same way you read `MASTER_GUIDE.md`.
> That file explains the Python brain. This file explains the screen in the browser.
>
> Stack: React 19 + Vite + React Router. Function components only.

---

## Table of Contents

1. [Big Picture](#1-big-picture)
2. [Five React Ideas You Need](#2-five-react-ideas-you-need)
3. [Folder Map — Each File and Why It Exists](#3-folder-map--each-file-and-why-it-exists)
4. [How the Page Starts](#4-how-the-page-starts)
5. [File by File](#5-file-by-file)
6. [Full Flow — Open, Sign Up, Chat, Refresh, Sign Out](#6-full-flow--open-sign-up-chat-refresh-sign-out)
7. [Which Hook We Use, and Why](#7-which-hook-we-use-and-why)
8. [Where Data Lives](#8-where-data-lives)
9. [Walkthrough With One Real Question](#9-walkthrough-with-one-real-question)
10. [Small Words You Will See in the Code](#10-small-words-you-will-see-in-the-code)

---

## 1. Big Picture

The browser shows two screens.

| URL | Screen | File |
|---|---|---|
| `http://localhost:5173/` | Sign in / Sign up | `frontend/src/pages/AuthPage.jsx` |
| `http://localhost:5173/chat` | Chat | `frontend/src/pages/ChatPage.jsx` |

React draws those screens. FastAPI answers them. React never opens MongoDB, Redis, or Gemini.

```
You type in the browser
        │
        ▼
   React (port 5173)
        │
        ├── sign in / sign up  →  HTTP  POST /api/auth/...
        │
        └── chat question      →  WebSocket  /ws/chat
        │
        ▼
   Vite forwards both to FastAPI (port 8000)
        │
        ▼
   Python does the real work and sends a result back
        │
        ▼
   React saves that result in state and draws it
```

**Key idea:** React is a function that returns HTML. When data changes, React runs the function again and updates the screen. You keep the data in state. You do not reach into the page and edit a div by hand.

---

## 2. Five React Ideas You Need

### A component is a function that returns HTML

`AuthPage`, `ChatPage`, and `App` are functions. The HTML-like syntax inside them is called JSX. A component's job is one piece of the screen.

```jsx
export function AuthPage() {
  return <main>Sign in form</main>
}
```

### State is memory that redraws the screen

```jsx
const [email, setEmail] = useState("")
```

`email` is the current value. `setEmail("fenil@mail.com")` saves a new value. React then runs the component function again, and the input shows the new email.

We use `useState` because the screen must change when the user types, when an error arrives, or when a chat bubble is added.

### Props are values a parent passes into a child

```jsx
<ProtectedRoute>
  <ChatPage />
</ProtectedRoute>
```

Inside `ProtectedRoute`, `children` is `<ChatPage />`. The parent passed that child in. We use props when a component needs data from the component above it.

### A hook is a function whose name starts with `use`

`useState`, `useEffect`, `useRef`, `useContext`, `useNavigate`, and our own `useChatSocket` are hooks. Hooks let a function component remember things and talk to the browser. They are called at the top of the component, every time it renders.

### Context is one shared box

Sign-in happens on one page. The chat page needs the same user and token. `AuthProvider` holds that data once, above both pages. Any child calls `useAuth()` and reads it. We use context so we do not pass `user` and `token` through every component by hand.

---

## 3. Folder Map — Each File and Why It Exists

```
frontend/
  index.html                 the one real HTML page; it has <div id="root">
  vite.config.js             forwards /api and /ws to FastAPI during development
  src/
    main.jsx                 starts React and wraps the app
    App.jsx                  chooses the page from the URL
    styles.css               colors and layout only
    lib/api.js               one function for every HTTP call
    auth/AuthContext.jsx     who is logged in, plus signIn / signUp / signOut
    auth/ProtectedRoute.jsx  sends you home if you open /chat while logged out
    pages/AuthPage.jsx       the form
    pages/ChatPage.jsx       the chat screen
    chat/useChatSocket.js    open the socket, keep the bubbles, send a question
```

| File | Why it exists |
|---|---|
| `index.html` | The browser needs one HTML file. React fills `#root`. |
| `vite.config.js` | The page is on port 5173 and FastAPI is on port 8000. The proxy makes them look like one site, so the browser allows the call. |
| `main.jsx` | This is the front door. Order of wrappers is decided here. |
| `App.jsx` | Routing stays in one small file. Pages stay free of "which URL am I?". |
| `api.js` | Every sign-in call needs the same JSON headers and the same error reading. One function does that. |
| `AuthContext.jsx` | Login is shared. The form writes it. The chat page reads it. |
| `ProtectedRoute.jsx` | Typing `/chat` in the address bar must not open chat with no user. |
| `AuthPage.jsx` | One form does both sign in and sign up. The mode switch is local to this page. |
| `ChatPage.jsx` | Draws the header, the bubbles, and the input. It does not know how the socket works. |
| `useChatSocket.js` | The socket opens, closes, and saves messages. That logic is long, so it lives in its own hook. The page stays easy to read. |
| `styles.css` | Looks. Change a class here and the matching `className` in a component changes color. No data flow lives in this file. |

---

## 4. How the Page Starts

`index.html` loads one script:

```html
<div id="root"></div>
<script type="module" src="/src/main.jsx"></script>
```

`main.jsx` then builds this tree:

```
StrictMode
  BrowserRouter          watches the URL
    AuthProvider         holds user + token
      App                picks AuthPage or ChatPage
```

Why this order:

1. `BrowserRouter` is outside everything that calls `useNavigate()` or `<Route>`. Those tools only work inside the router.
2. `AuthProvider` is outside `App`, so both routes can call `useAuth()`.
3. `App` is inside both, so it can read the URL and the login.

`StrictMode` is a development helper. In dev, React mounts a page, cleans it up, and mounts it again. That is why the server log can show the chat socket connect twice. The cleanup closes the first one. A production build connects once.

---

## 5. File by File

### `vite.config.js` — the hallway between the page and Python

The React code calls `/api/auth/signin` and opens `/ws/chat` on port 5173.

Vite does this:

```
/api/auth/signin   →   http://127.0.0.1:8000/auth/signin
/ws/chat           →   ws://127.0.0.1:8000/ws/chat
```

The `rewrite` line removes `/api` before the request reaches FastAPI. Python routes are `/auth/signin`, not `/api/auth/signin`.

We use a proxy in development so the browser sees one origin. In production you would put the real API host in config. The React code can stay on relative paths.

### `lib/api.js` — every HTTP call

`api(path, { method, body, token })` uses the browser's built-in `fetch`.

What it does, in order:

1. Sets `Content-Type: application/json`.
2. If you passed a token, sets `Authorization: Bearer <token>`. Sign-out uses this.
3. `JSON.stringify(body)` turns `{ email, password }` into text, because `fetch` sends text.
4. Reads the JSON reply.
5. If the status is an error, throws `Error` with FastAPI's `detail` string. The form shows that string.

Sign-in and sign-up use `api()`. The chat question does not. A question goes through the WebSocket, because that connection stays open and the server can push "thinking" and then the answer.

### `auth/AuthContext.jsx` — the login box

This file creates a React context and a provider.

```jsx
const AuthContext = createContext(null)
```

`AuthProvider` keeps two pieces of state:

| State | What it is | Where it is also saved |
|---|---|---|
| `user` | `{ user_id, name, email }` | `sessionStorage` key `"user"` |
| `token` | random string from FastAPI | `sessionStorage` key `"token"` |

`useState(readStoredUser)` runs `readStoredUser` once, on the first render. If this tab already signed in, the user is restored before the first paint. That is why a refresh stays on the chat page.

Functions on the provider:

| Function | Why |
|---|---|
| `remember(session)` | Sign-in and sign-up both return `{ token, user }`. One function saves both places: React state and `sessionStorage`. |
| `signIn` | `POST /auth/signin`, then `remember`. |
| `signUp` | `POST /auth/signup`, then `remember`. |
| `signOut` | Clears React state and `sessionStorage`, then `POST /auth/signout` so Redis deletes the token. |
| `useAuth()` | The only way pages should read the box. If you call it outside the provider, it throws, which tells you the wrapper in `main.jsx` is missing. |

`sessionStorage` is used for the login because it lasts for this tab. A refresh keeps it. Closing the tab clears it.

The chat transcript uses `localStorage` instead, which lasts after the tab closes. Login and transcript are different lifetimes, so they use different stores.

### `auth/ProtectedRoute.jsx` — the door on `/chat`

```jsx
if (!user) return <Navigate to="/" replace />
return children
```

`App` wraps `ChatPage` in this component. We use it so the "are you signed in?" check lives in one place. `ChatPage` can assume `user` exists.

`replace` swaps the history entry. The blocked `/chat` visit does not remain as a back-button stop.

### `pages/AuthPage.jsx` — one form, two modes

Local state on this page:

| State | Why it exists |
|---|---|
| `mode` | `"signin"` or `"signup"`. The name field appears only in signup. |
| `name`, `email`, `password` | The text in the inputs. |
| `error` | The message from FastAPI, such as a wrong password. |
| `busy` | `true` while the request is running. The button disables so a double click does not send two sign-ups. |

These values belong to the form only. The chat page does not need them, so they stay here and not in context.

The inputs are **controlled**. `value={email}` means React owns the text. `onChange` calls `setEmail`. React renders again and the input shows the new value. We use this so submit reads `email` from state, and so we can clear or validate that text.

`onSubmit`:

1. `event.preventDefault()` keeps the browser from doing a full page reload. A reload would wipe React memory.
2. Calls `signUp` or `signIn`.
3. On success, `navigate("/chat")`.
4. On failure, `setError(err.message)`. `api()` put FastAPI's `detail` on that error.
5. `finally` sets `busy` back to false whether it worked or failed.

If `user` is already set, the page returns `<Navigate to="/chat" />` and the form is not shown. That covers a refresh while you are still signed in.

The bottom button has `type="button"`. A button inside a form submits the form unless the type says otherwise. This button only flips `mode`.

### `pages/ChatPage.jsx` — the screen, not the socket

It reads three things from `useAuth()`: `user`, `token`, `signOut`.

It reads three things from `useChatSocket(token, user.user_id)`:

| Value | Why the page needs it |
|---|---|
| `messages` | The list of bubbles to draw. |
| `status` | The pill: `connecting`, `ready`, `thinking`, or `disconnected`. |
| `sendMessage` | What the form calls when you press Send. |

`draft` is a separate `useState`. It is only the text currently in the box. It becomes a message when you submit. We keep it separate so typing does not rewrite the bubble list on every key.

`messages.map` turns each item into a bubble. `key={message.id}` gives React a stable name for each bubble. When a new answer is appended, React adds one bubble and leaves the old ones in place.

`message.cached` is true when FastAPI served the Redis last-5 cache. The page shows the "From cache" tag from that flag.

Send stays disabled while `status` is not `"ready"`. One question is in flight at a time, which matches one agent run on the server.

### `chat/useChatSocket.js` — the socket lifecycle

This is a custom hook. `ChatPage` stays short because the connection rules live here.

**State**

- `messages` starts from `localStorage` key `chat:messages:<user_id>`. The function form of `useState` runs once, so the old bubbles are present on the first paint.
- `status` starts as `"connecting"`.

**Ref**

```jsx
const socketRef = useRef(null)
```

The WebSocket object is stored in a ref. Changing a ref does not redraw the page. We use a ref because the screen never displays the socket itself. The screen displays `messages` and `status`, and those are state.

**Effect 1 — save bubbles**

```jsx
useEffect(() => {
  localStorage.setItem(STORAGE_PREFIX + userId, JSON.stringify(messages))
}, [userId, messages])
```

`useEffect` runs after render. This one runs again whenever `userId` or `messages` changes. We use it to copy the bubble list into the browser. The next refresh reads that copy.

The key includes `userId` so two accounts on one browser keep two transcripts.

**Effect 2 — open and close the socket**

Runs after the chat page is on screen, and again if `token` changes.

1. Build `ws://localhost:5173/ws/chat` (or `wss://` on https).
2. On open, send `{ "type": "auth", "token": "..." }`.
3. On each server message, update status or append an assistant bubble.
4. Return a cleanup function that calls `socket.close()`.

We use `useEffect` for the socket because opening a connection is a side effect. It talks to the network. It is not something you do while calculating the HTML. The cleanup is why leaving the chat page, or signing out, does not leave a hidden connection open.

The browser WebSocket API cannot set an `Authorization` header. That is why the token is the first socket message. Sign-out is a normal `fetch`, so it can use the header.

**`sendMessage`**

1. If the socket is not open, return.
2. Append a user bubble with `setMessages(previous => [...previous, bubble])`.
3. Set status to `"thinking"`.
4. Send `{ "type": "question", "message": text }`.

The `...previous` copy matters. React state is replaced with a new array. We copy the old bubbles and add one at the end. The answer arrives later, inside `onmessage`, and is appended the same way.

The question JSON has no `user_id`. The server already turned the token into a user id when the socket said `ready`.

### `App.jsx` — the URL switch

```jsx
<Route path="/" element={<AuthPage />} />
<Route path="/chat" element={<ProtectedRoute><ChatPage /></ProtectedRoute>} />
```

`Routes` looks at the address bar and renders one match. We keep this file tiny so "what is on the screen" is obvious in one place.

---

## 6. Full Flow — Open, Sign Up, Chat, Refresh, Sign Out

### A. You open `http://localhost:5173/`

1. `index.html` loads `main.jsx`.
2. `AuthProvider` reads `sessionStorage`. First visit: no user, no token.
3. The URL is `/`, so `App` renders `AuthPage`.
4. `user` is empty, so the form is shown. Mode starts as `"signin"`.

### B. You press "Need an account? Sign up"

`setMode("signup")`. React renders again. The name field appears because `isSignUp` is true. Email and password were already on the form.

### C. You submit the sign-up form

1. `onSubmit` runs. `busy` becomes true. The button reads "Please wait…".
2. `signUp(name, email, password)` calls `api("/auth/signup", ...)`.
3. Vite forwards that to FastAPI `POST /auth/signup`.
4. FastAPI returns `{ token, user }`.
5. `remember` writes both into React state and `sessionStorage`.
6. `navigate("/chat")` changes the URL.
7. `ProtectedRoute` sees a user and renders `ChatPage`.

If the email exists, FastAPI returns an error. `api()` throws. `setError` shows the message. `busy` becomes false. You stay on the form.

Sign-in is the same path with `signIn` and `POST /auth/signin`. The name field is not sent.

### D. The chat page connects

1. `useState` loads old bubbles for this `user_id` from `localStorage`. A brand-new user has an empty list.
2. The socket effect opens `/ws/chat`.
3. On open it sends `{ type: "auth", token }`.
4. FastAPI checks Redis. The token maps to your `user_id`.
5. The server sends `{ type: "ready" }`.
6. `setStatus("ready")`. The Send button can turn on once the input has text.

### E. You send a question

1. `onSubmit` trims the draft and calls `sendMessage`.
2. Your bubble appears at once. Status becomes `thinking`. The box is cleared.
3. The socket sends `{ type: "question", message: "..." }`.
4. The server later sends `{ type: "answer", answer, cached }`.
5. `onmessage` appends the assistant bubble and sets status back to `ready`.
6. The messages effect writes the new list to `localStorage`.

### F. You refresh the tab

1. React memory is gone. The page starts from step A again.
2. `sessionStorage` still has `token` and `user`, so `AuthProvider` restores them.
3. `AuthPage` sees a user and redirects to `/chat`.
4. `useChatSocket` reads the bubbles from `localStorage` before the first paint.
5. A new socket opens and authenticates with the same token.

The conversation is visible immediately. The status pill goes `connecting`, then `ready`, because the socket is a new connection even though the bubbles were saved.

### G. You sign out

1. `signOut` clears `user` and `token` in React and in `sessionStorage`.
2. It calls `POST /auth/signout` with the bearer token. Redis deletes `session:<token>`.
3. `navigate("/")` shows the form.
4. The socket effect cleans up because `token` changed, and `socket.close()` runs.

The bubbles stay in `localStorage` under your `user_id`. The next sign-in on this browser shows them again. A different account uses a different key.

---

## 7. Which Hook We Use, and Why

| Hook | Where | Why this one |
|---|---|---|
| `useState` | form fields, `busy`, `error`, `messages`, `status`, `draft` | The screen must redraw when the value changes. |
| `useEffect` | save messages; open and close the socket | Those jobs talk to the browser or the network after render. |
| `useRef` | `socketRef` | Remember the socket without a redraw. |
| `useContext` inside `useAuth` | both pages | Read the shared login box. |
| `useNavigate` | `AuthPage`, `ChatPage` | Change the URL after sign-in or sign-out. |
| `useChatSocket` | `ChatPage` | Our own hook. It groups the socket rules so the page only draws. |

We did not add Redux or another state library. Two pages share one small box of login data. Context is enough for that.

---

## 8. Where Data Lives

```
React state          lives until the next refresh
sessionStorage       login for this tab; survives refresh; cleared when the tab closes
localStorage         chat bubbles per user_id; survives refresh and a closed tab
Redis (server)       session token and the last 5 answers
MongoDB (server)     the user document and the orders
```

The browser stores the token. It does not store the password after submit. The password goes to FastAPI once. The server stores a hash.

The chat page never puts `user_id` in the question message. It sends the token. The server looks up the id. That matches the rule in the Python guide: identity comes from the session, not from the question text.

---

## 9. Walkthrough With One Real Question

You are signed in as Fenil, `USER-8624C7`. The input contains `What is the refund policy?`. You press Send.

```
ChatPage.onSubmit
  draft.trim()  →  "What is the refund policy?"
  sendMessage(text)
        │
        ▼
useChatSocket.sendMessage
  messages = [ ...old, { role: "user", text } ]
  status   = "thinking"
  socket sends { type: "question", message: "What is the refund policy?" }
        │
        ▼
Vite proxy  →  FastAPI /ws/chat
  token was already checked
  user_id = USER-8624C7
  answer_question(...)        ← Python guide, cache then agent
        │
        ▼
socket receives { type: "answer", answer: "...", cached: false }
        │
        ▼
onmessage
  messages = [ ...old, user bubble, { role: "assistant", text, cached: false } ]
  status   = "ready"
        │
        ▼
useEffect writes localStorage["chat:messages:USER-8624C7"]
ChatPage maps messages into bubbles
```

Ask the same sentence again. The Python cache returns `cached: true`. The same `onmessage` runs. The bubble gets the extra "From cache" tag because `message.cached` is true.

---

## 10. Small Words You Will See in the Code

| Word | Plain meaning |
|---|---|
| JSX | HTML written inside a JavaScript function. |
| render | React running your component function to describe the screen. |
| state | A value React remembers. Changing it renders again. |
| setter | `setEmail`, `setMessages`. The function that stores the next value. |
| props | Inputs a parent gives a child, including `children`. |
| children | The JSX placed between an opening tag and a closing tag. |
| controlled input | An input whose `value` is state. |
| context | A box of data available to every child under the provider. |
| provider | The component that fills the box. Ours is `AuthProvider`. |
| hook | A `use*` function. |
| effect | Code that runs after render. Ours opens the socket and saves messages. |
| cleanup | The function an effect returns. Ours closes the socket. |
| ref | A box that survives renders and does not, by itself, cause a render. |
| key | The id React uses to match list items across renders. |
| navigate | Change the URL without a full browser reload. |

Read the files in this order after this guide:

1. `frontend/src/main.jsx`
2. `frontend/src/App.jsx`
3. `frontend/src/lib/api.js`
4. `frontend/src/auth/AuthContext.jsx`
5. `frontend/src/pages/AuthPage.jsx`
6. `frontend/src/auth/ProtectedRoute.jsx`
7. `frontend/src/pages/ChatPage.jsx`
8. `frontend/src/chat/useChatSocket.js`

The comments in those files match the steps above.
