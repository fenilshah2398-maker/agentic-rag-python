import { Route, Routes } from "react-router-dom"
import { ProtectedRoute } from "./auth/ProtectedRoute.jsx"
import { AuthPage } from "./pages/AuthPage.jsx"
import { ChatPage } from "./pages/ChatPage.jsx"

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<AuthPage />} />
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