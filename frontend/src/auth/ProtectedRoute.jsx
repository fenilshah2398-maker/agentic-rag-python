import { Navigate } from "react-router-dom"
import { useAuth } from "./AuthContext.jsx"

export function ProtectedRoute({ children }) {
  const { user } = useAuth()
  if (!user) {
    return <Navigate to="/" replace />
  }
  return children
}