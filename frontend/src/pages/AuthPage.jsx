// One screen, two modes. mode is "signin" or "signup".
// The name field is rendered only while mode is "signup".
//
// The inputs are controlled: React state holds the text, and the
// input's value is that state. Typing calls setEmail / setPassword,
// React renders again, and the input shows the new text.
import { useState } from "react"
import { Navigate, useNavigate } from "react-router-dom"
import { useAuth } from "../auth/AuthContext.jsx"

export function AuthPage() {
  const { user, signIn, signUp } = useAuth()
  const navigate = useNavigate()

  const [mode, setMode] = useState("signin")
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  // busy disables the button while the request is in flight.
  const [busy, setBusy] = useState(false)

  // Already signed in (including after a refresh): skip the form.
  if (user) {
    return <Navigate to="/chat" replace />
  }

  async function onSubmit(event) {
    // Stop the browser from reloading the page on submit.
    event.preventDefault()
    setError("")
    setBusy(true)
    try {
      if (mode === "signup") {
        await signUp(name, email, password)
      } else {
        await signIn(email, password)
      }
      // remember() already saved the token. Now show the chat page.
      navigate("/chat")
    } catch (err) {
      // api() throws the FastAPI "detail" string, for example a bad password.
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const isSignUp = mode === "signup"

  return (
    <main className="auth-page">
      <form className="card" onSubmit={onSubmit}>
        <p className="eyebrow">Agentic RAG</p>
        <h1>{isSignUp ? "Create your account" : "Welcome back"}</h1>
        <p className="muted">
          {isSignUp
            ? "Orders and policy answers are stored against your user id."
            : "Sign in to open the chat."}
        </p>

        {isSignUp && (
          <label>
            Name
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              autoComplete="name"
              required
            />
          </label>
        )}

        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            required
          />
        </label>

        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete={isSignUp ? "new-password" : "current-password"}
            minLength={8}
            required
          />
        </label>

        {error && <p className="error">{error}</p>}

        <button type="submit" disabled={busy}>
          {busy ? "Please wait…" : isSignUp ? "Create account" : "Sign in"}
        </button>

        {/* type="button" so this click does not submit the form. */}
        <button
          type="button"
          className="text-button"
          onClick={() => {
            setMode(isSignUp ? "signin" : "signup")
            setError("")
          }}
        >
          {isSignUp ? "Already have an account? Sign in" : "Need an account? Sign up"}
        </button>
      </form>
    </main>
  )
}
