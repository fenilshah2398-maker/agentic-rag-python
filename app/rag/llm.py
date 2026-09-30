"""
Chat LLM factory — the reasoning model used by agent_node.

Uses Google Gemini via langchain-google-genai.
temperature=0 → more deterministic, better for factual enterprise Q&A.

This object alone cannot call tools until nodes.py does: llm.bind_tools(tools)
"""

from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings


llm = ChatGoogleGenerativeAI(
    # Model id from .env (e.g. gemini-3.1-flash-lite)
    model=settings.gemini_llm_model,
    google_api_key=settings.gemini_api_key,
    # Low temperature = less creative invention, more consistent tool use
    temperature=0,
)
