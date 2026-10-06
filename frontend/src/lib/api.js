/**
 * Every HTTP call goes through here.
 * path is the FastAPI path: "/auth/signin"
 * The "/api" prefix is what Vite strips before forwarding.
 */
export async function api(path, { method = "GET", body, token } = {}) {
    const headers = { "Content-Type": "application/json" }
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }
  
    const response = await fetch(`/api${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    })
  
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      const detail = data.detail
      const message = typeof detail === "string" ? detail : "Request failed"
      throw new Error(message)
    }
    return data
  }