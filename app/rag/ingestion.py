"""
Offline document preparation for policy RAG (no network writes here).

Pipeline (called by scripts/ingest_policies.py):
  1. load_policy_documents() — read data/policies/*.md into LangChain Documents
  2. split_documents()       — chunk long text for better embedding / retrieval

Why chunk?
  Embeddings work best on focused passages. Overlap keeps sentences that would
  otherwise be cut at chunk boundaries.
"""

from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter
)


def load_policy_documents():
    """
    Load every markdown policy file as a Document.

    metadata.source is kept so search_policy can tell the LLM which file
    a chunk came from (e.g. refund.md).
    """

    documents = []

    # Relative to process cwd (run scripts from project root)
    policy_dir = Path("data/policies")

    for file_path in policy_dir.glob("*.md"):

        content = file_path.read_text(
            encoding="utf-8"
        )

        document = Document(
            page_content=content,  # raw text that will be embedded
            metadata={
                "source": file_path.name,
                "document_type": "policy",
            },
        )

        documents.append(document)

    return documents


def split_documents(documents):
    """
    Split Documents into overlapping chunks.

    chunk_size=500  → max characters per chunk (approx)
    chunk_overlap=100 → shared chars between neighbors for context continuity

    RecursiveCharacterTextSplitter tries to split on paragraphs/sentences
    before hard-cutting mid-word when possible.
    """

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
    )

    return splitter.split_documents(documents)
