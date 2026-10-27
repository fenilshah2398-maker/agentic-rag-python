// Custom hook: a function whose name starts with "use".
// ChatPage calls it and gets { messages, status, sendMessage }.
//
// Two kinds of storage:
//   localStorage  — the bubbles, so a refresh still shows the conversation
//   useRef        — the live WebSocket object, which the screen does not draw
import { useEffect, useRef, useState } from "react"

const STORAGE_PREFIX = "chat:messages:"

function readMessages(userId) {
  if (!userId) return []
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + userId)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function useChatSocket(token, userId) {
  // Read the saved transcript once, before the first paint.
  const [messages, setMessages] = useState(() => readMessages(userId))
  const [status, setStatus] = useState("connecting")
  // A ref change does not re-render the page. State is for what the screen shows.
  const socketRef = useRef(null)

  // Every time the bubble list changes, write it under this user's id.
  // Another account on this browser has a different key.
  useEffect(() => {
    if (!userId) return
    localStorage.setItem(STORAGE_PREFIX + userId, JSON.stringify(messages))
  }, [userId, messages])

  // Open the socket after the page is on screen. The returned function
  // runs when you leave the page and closes the connection.
  useEffect(() => {
    if (!token) return

    const protocol = window.location.protocol === "https:" ? "wss" : "ws"
    // Same host as the page (localhost:5173). Vite forwards /ws to FastAPI.
    const socket = new WebSocket(`${protocol}://${window.location.host}/ws/chat`)
    socketRef.current = socket

    // The browser WebSocket API cannot set an Authorization header,
    // so the token is the first message on the connection.
    socket.onopen = () => {
      socket.send(JSON.stringify({ type: "auth", token }))
    }

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data)

      // Server accepted the token and now knows our user_id.
      if (data.type === "ready") setStatus("ready")
      // "thinking" while the agent runs, or an error string.
      if (data.type === "status") setStatus(data.text)
      if (data.type === "error") setStatus(data.text)

      if (data.type === "answer") {
        setStatus("ready")
        // Copy the old list and add one bubble. React state is replaced, not edited.
        setMessages((previous) => [
          ...previous,
          { id: crypto.randomUUID(), role: "assistant", text: data.answer, cached: data.cached },
        ])
      }
    }

    socket.onclose = () => setStatus("disconnected")

    return () => {
      socket.close()
    }
  }, [token])

  function sendMessage(text) {
    const socket = socketRef.current
    if (!socket || socket.readyState !== WebSocket.OPEN) return

    // Show the user's bubble immediately. The answer arrives later in onmessage.
    setMessages((previous) => [
      ...previous,
      { id: crypto.randomUUID(), role: "user", text },
    ])
    setStatus("thinking")
    // No user_id here. The server already mapped the token to the user.
    socket.send(JSON.stringify({ type: "question", message: text }))
  }

  return { messages, status, sendMessage }
}
