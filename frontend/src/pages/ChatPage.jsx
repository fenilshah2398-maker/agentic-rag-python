import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "../auth/AuthContext.jsx"
import { useChatSocket } from "../chat/useChatSocket.js"

export function ChatPage() {
  const { user, token, signOut } = useAuth()
  const navigate = useNavigate()
  const { messages, status, sendMessage } = useChatSocket(token, user.user_id)
  const [draft, setDraft] = useState("")

  async function onSignOut() {
    await signOut()
    navigate("/")
  }

  function onSubmit(event) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || status === "thinking" || status === "connecting") return
    sendMessage(text)
    setDraft("")
  }

  return (
    <main className="chat-page">
      <header className="chat-bar">
        <div>
          <p className="eyebrow">Signed in</p>
          <strong>{user.name}</strong>
          <span className="muted"> {user.email}</span>
        </div>
        <div className="chat-bar-actions">
          <span className={`status status-${status}`}>{status}</span>
          <button type="button" onClick={onSignOut}>
            Sign out
          </button>
        </div>
      </header>

      <section className="transcript" aria-live="polite">
        {messages.length === 0 && (
          <p className="muted empty">Ask about a refund, a return, or today’s orders.</p>
        )}
        {messages.map((message) => (
          <article key={message.id} className={`bubble ${message.role}`}>
            <p>{message.text}</p>
            {message.cached && <span className="tag">From cache</span>}
          </article>
        ))}
      </section>

      <form className="composer" onSubmit={onSubmit}>
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask a question"
          aria-label="Message"
        />
        <button type="submit" disabled={!draft.trim() || status !== "ready"}>
          Send
        </button>
      </form>
    </main>
  )
}