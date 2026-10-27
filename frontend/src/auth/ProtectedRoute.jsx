// Wraps the chat page. If nobody is signed in, the URL goes back to /.
// replace means that blocked visit does not stay in the back-button history.
import { Navigate } from "react-router-dom"
import { useAuth } from "./AuthContext.jsx"

export function ProtectedRoute({ children }) {
  const { user } = useAuth()
  if (!user) {
    return <Navigate to="/" replace />
  }
  return children
}
