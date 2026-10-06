import { createContext, useContext, useState } from "react"
import { api } from "../lib/api.js"

const AuthContext = createContext(null)

function readStoredUser() {
  const raw = sessionStorage.getItem("user")
  return raw ? JSON.parse(raw) : null
}

export function AuthProvider({ children }) {
  // The function form runs once, on the first render, and reads the saved login.
  const [user, setUser] = useState(readStoredUser)
  const [token, setToken] = useState(() => sessionStorage.getItem("token"))

  function remember(session) {
    sessionStorage.setItem("token", session.token)
    sessionStorage.setItem("user", JSON.stringify(session.user))
    setToken(session.token)
    setUser(session.user)
  }

  async function signIn(email, password) {
    remember(await api("/auth/signin", { method: "POST", body: { email, password } }))
  }

  async function signUp(name, email, password) {
    remember(
      await api("/auth/signup", {
        method: "POST",
        body: { name, email, password },
      }),
    )
  }

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