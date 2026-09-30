"""
Application settings loaded from environment / .env

pydantic-settings maps env vars to typed fields automatically:
  GEMINI_API_KEY          → gemini_api_key
  GEMINI_LLM_MODEL        → gemini_llm_model
  GEMINI_EMBEDDING_MODEL  → gemini_embedding_model
  MONGODB_URI             → mongodb_uri
  MONGODB_DATABASE        → mongodb_database
  REDIS_URL               → redis_url

Never hardcode secrets in source. Keep them in .env (gitignored).
After changing .env, restart uvicorn / the debugger so values reload.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Google Gemini credentials + model ids
    gemini_api_key: str
    gemini_llm_model: str
    gemini_embedding_model: str

    # MongoDB Atlas connection (mongodb+srv://...) and database name
    # Local mongodb://localhost will NOT support $vectorSearch
    mongodb_uri: str
    mongodb_database: str

    # Reserved for future session memory / caching
    redis_url: str

    class Config:
        # Load key=value pairs from project-root .env
        env_file = ".env"


# Singleton imported across the app: from app.config import settings
settings = Settings()
