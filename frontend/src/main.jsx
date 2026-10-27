// First file the browser runs. It mounts React into <div id="root">.
//
// Wrapper order matters:
//   BrowserRouter  — lets pages read and change the URL (/ and /chat)
//   AuthProvider   — holds the logged-in user so both pages can read it
//   App            — chooses which page to show
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import App from "./App.jsx"
import { AuthProvider } from "./auth/AuthContext.jsx"
import "./styles.css"

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
