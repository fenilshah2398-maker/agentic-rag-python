/**
 * One function for every HTTP call to FastAPI.
 *
 * path is the Python route, for example "/auth/signin".
 * We prefix "/api" because Vite forwards /api/* to port 8000
 * and strips that prefix. The browser calls:
 *   http://localhost:5173/api/auth/signin
 * FastAPI receives:
 *   http://127.0.0.1:8000/auth/signin
 *
 * token, when present, is sent as:
 *   Authorization: Bearer <token>
 * Sign-out uses this. The chat socket cannot set headers, so it
 * sends the token in its first message instead.
 */
export async function api(path, { method = "GET", body, token } = {}) {
  const headers = { "Content-Type": "application/json" }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(`/api${path}`, {
    method,
    headers,
    // fetch wants a string body. JSON.stringify turns { email, password } into text.
    body: body ? JSON.stringify(body) : undefined,
  })

  // A failed response may still be JSON, with FastAPI's "detail" message.
  // If the body is not JSON, fall back to an empty object.
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data.detail
    const message = typeof detail === "string" ? detail : "Request failed"
    throw new Error(message)
  }
  return data
}
