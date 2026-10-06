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
  const [busy, setBusy] = useState(false)

  if (user) {
    return <Navigate to="/chat" replace />
  }

  async function onSubmit(event) {
    event.preventDefault()
    setError("")
    setBusy(true)
    try {
      if (mode === "signup") {
        await signUp(name, email, password)
      } else {
        await signIn(email, password)
      }
      navigate("/chat")
    } catch (err) {
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