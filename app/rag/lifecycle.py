"""
Document lifecycle — do not re-embed a file that did not change.

Each policy file gets:
  content_hash  — sha256 of the markdown
  version       — 1, 2, 3... increment when the hash changes
  active        — True on the chunks we just wrote

If the hash matches last ingest, we skip that file.
If it changed, we delete that file's old chunks and write new ones.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone


def file_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def current_version(source: str) -> dict | None:
    from app.db.mongo import policy_versions

    return await policy_versions.find_one({"source": source})


async def replace_source_chunks(source: str, chunks, vector_store) -> int:
    from app.db.mongo import policy_collection

    deleted = await policy_collection.delete_many({"source": source})
    if chunks:
        await vector_store.aadd_documents(chunks)
    return deleted.deleted_count


async def bump_version(source: str, content_hash: str) -> int:
    from app.db.mongo import policy_versions

    now = datetime.now(timezone.utc)
    existing = await current_version(source)
    version = 1 if not existing else int(existing.get("version") or 0) + 1
    await policy_versions.update_one(
        {"source": source},
        {
            "$set": {
                "source": source,
                "content_hash": content_hash,
                "version": version,
                "updated_at": now,
            }
        },
        upsert=True,
    )
    return version
