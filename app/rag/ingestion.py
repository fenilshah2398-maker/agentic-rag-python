"""
Offline document preparation for policy RAG (no network writes here).

Pipeline (called by scripts/ingest_policies.py):
  1. load_policy_documents() — read data/policies/*.md into LangChain Documents
  2. split_documents()       — one chunk per markdown heading section

Why headings instead of a 500-character cut?
  A character splitter can glue "Refund window" to the next topic, or
  cut a sentence in half. A heading splitter keeps one idea per chunk
  and writes that heading into metadata.section.

Each chunk then carries:
  source  — filename, e.g. refund.md
  policy  — file stem, e.g. refund
  section — the ## heading, e.g. Refund window
"""

from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter

from app.rag.lifecycle import file_hash


POLICY_DIR = Path("data/policies")


def load_policy_documents():
    """
    Load every markdown policy file as a Document.

    policy is the filename without .md so later filters can say
    "only search policy=refund" without parsing the path.
    """

    documents = []

    for file_path in sorted(POLICY_DIR.glob("*.md")):
        content = file_path.read_text(encoding="utf-8")
        documents.append(
            Document(
                page_content=content,
                metadata={
                    "source": file_path.name,
                    "policy": file_path.stem,
                    "document_type": "policy",
                    "content_hash": file_hash(content),
                },
            )
        )

    return documents


def split_documents(documents):
    """
    Split on # and ##. Do not cut on a character budget.

    MarkdownHeaderTextSplitter puts the heading text into metadata
    and (with strip_headers=False) also leaves it in the chunk body
    so the embedding sees the words "Refund window".
    """

    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "title"),
            ("##", "section"),
        ],
        strip_headers=False,
    )

    chunks = []
    for document in documents:
        parts = header_splitter.split_text(document.page_content)
        for part in parts:
            section = (
                part.metadata.get("section")
                or part.metadata.get("title")
                or "General"
            )
            chunks.append(
                Document(
                    page_content=part.page_content.strip(),
                    metadata={
                        "source": document.metadata["source"],
                        "policy": document.metadata["policy"],
                        "section": section,
                        "document_type": "policy",
                        "active": True,
                        "content_hash": document.metadata.get("content_hash"),
                        "version": document.metadata.get("version"),
                    },
                )
            )

    return chunks
