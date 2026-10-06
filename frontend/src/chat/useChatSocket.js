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
  // Read the saved transcript once, before the first paint, so refresh
  // shows the old messages instead of an empty page.
  const [messages, setMessages] = useState(() => readMessages(userId))
  const [status, setStatus] = useState("connecting")
  const socketRef = useRef(null)

  useEffect(() => {
    if (!userId) return
    localStorage.setItem(STORAGE_PREFIX + userId, JSON.stringify(messages))
  }, [userId, messages])

  useEffect(() => {
    if (!token) return

    const protocol = window.location.protocol === "https:" ? "wss" : "ws"
    const socket = new WebSocket(`${protocol}://${window.location.host}/ws/chat`)
    socketRef.current = socket

    socket.onopen = () => {
      socket.send(JSON.stringify({ type: "auth", token }))
    }

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === "ready") setStatus("ready")
      if (data.type === "status") setStatus(data.text)
      if (data.type === "error") setStatus(data.text)

      if (data.type === "answer") {
        setStatus("ready")
        setMessages((previous) => [
          ...previous,
          { id: crypto.randomUUID(), role: "assistant", text: data.answer, cached: data.cached },
        ])
      }
    }

    socket.onclose = () => setStatus("disconnected")

    // Runs when you leave the chat page, or before React runs this effect again.
    return () => {
      socket.close()
    }
  }, [token])

  function sendMessage(text) {
    const socket = socketRef.current
    if (!socket || socket.readyState !== WebSocket.OPEN) return

    setMessages((previous) => [
      ...previous,
      { id: crypto.randomUUID(), role: "user", text },
    ])
    setStatus("thinking")
    socket.send(JSON.stringify({ type: "question", message: text }))
  }

  return { messages, status, sendMessage }
}