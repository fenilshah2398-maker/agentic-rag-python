"""
HTTP request body schema for POST /chat.

FastAPI uses this Pydantic model to:
  - validate incoming JSON
  - auto-generate Swagger docs at /docs
  - reject bad payloads before the agent runs

Example body:
  {
    "user_id": "USER-001",
    "message": "What did I order today?"
  }
"""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    # Authenticated user id — becomes AgentState.user_id (trusted, injected into tools)
    user_id: str

    # Natural language question from the client
    message: str
