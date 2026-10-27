// Shared login box for both pages.
//
// AuthProvider wraps the app in main.jsx. Any child can call useAuth()
// and receive { user, token, signIn, signUp, signOut }.
//
// sessionStorage keeps the login for this browser tab.
// A refresh reads it back. Closing the tab clears it.
import { createContext, useContext, useState } from "react"
import { api } from "../lib/api.js"

const AuthContext = createContext(null)

function readStoredUser() {
  const raw = sessionStorage.getItem("user")
  return raw ? JSON.parse(raw) : null
}

export function AuthProvider({ children }) {
  // These run once, on the first render, before the page paints.
  // If a previous sign-in saved a session, the user is already logged in.
  const [user, setUser] = useState(readStoredUser)
  const [token, setToken] = useState(() => sessionStorage.getItem("token"))

  // Both sign-in and sign-up get the same shape back: { token, user }.
  function remember(session) {
    sessionStorage.setItem("token", session.token)
    sessionStorage.setItem("user", JSON.stringify(session.user))
    setToken(session.token)
    setUser(session.user)
  }

  // POST /auth/signin  ->  remember the session FastAPI created in Redis.
  async function signIn(email, password) {
    remember(await api("/auth/signin", { method: "POST", body: { email, password } }))
  }

  // POST /auth/signup  ->  MongoDB stores the user, Redis stores the token.
  async function signUp(name, email, password) {
    remember(
      await api("/auth/signup", {
        method: "POST",
        body: { name, email, password },
      }),
    )
  }

  // Clear the browser first, then tell Redis to delete the token.
  // After this, the old token cannot open a chat socket.
  async function signOut() {
    const current = token
    setUser(null)
    setToken(null)
    sessionStorage.removeItem("token")
    sessionStorage.removeItem("user")
    if (current) {
      await api("/auth/signout", { method: "POST", token: current }).catch(() => {})
    }
  }

  // children is whatever this provider wraps. Here that is <App />.
  return (
    <AuthContext.Provider value={{ user, token, signIn, signUp, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) {
    throw new Error("useAuth must be used inside AuthProvider")
  }
  return value
}
