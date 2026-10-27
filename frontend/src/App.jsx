// App only picks the screen. The form lives in AuthPage.
// The messages and socket live in ChatPage.
import { Route, Routes } from "react-router-dom"
import { ProtectedRoute } from "./auth/ProtectedRoute.jsx"
import { AuthPage } from "./pages/AuthPage.jsx"
import { ChatPage } from "./pages/ChatPage.jsx"

export default function App() {
  return (
    <Routes>
      {/* http://localhost:5173/  */}
      <Route path="/" element={<AuthPage />} />
      {/* http://localhost:5173/chat — blocked until someone is signed in */}
      <Route
        path="/chat"
        element={
          <ProtectedRoute>
            <ChatPage />
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}
