// Custom hook: a function whose name starts with "use".
// ChatPage calls it and gets { messages, status, sendMessage, respondApproval }.
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
          {
            id: crypto.randomUUID(),
            role: "assistant",
            text: data.answer,
            cached: data.cached,
            cacheKind: data.cache_kind || null,
            trace: data.trace || null,
            sources: data.sources || [],
          },
        ])
      }

      if (data.type === "approval") {
        setStatus("ready")
        setMessages((previous) => [
          ...previous,
          {
            id: crypto.randomUUID(),
            role: "approval",
            text: data.message || `Cancel ${data.order_id}?`,
            approval: data,
          },
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

    setMessages((previous) => [
      ...previous,
      { id: crypto.randomUUID(), role: "user", text },
    ])
    setStatus("thinking")
    socket.send(JSON.stringify({ type: "question", message: text }))
  }

  function respondApproval(approved, approval) {
    const socket = socketRef.current
    if (!socket || socket.readyState !== WebSocket.OPEN) return
    setStatus("thinking")
    socket.send(
      JSON.stringify({
        type: "approval_response",
        approved,
        order_id: approval.order_id,
      }),
    )
  }

  return { messages, status, sendMessage, respondApproval }
}
