"""
Index policy markdown into Atlas, one file at a time.

    python -m scripts.ingest_policies
    python -m scripts.ingest_policies --dry-run

If a file's hash matches the last ingest, we skip it.
If it changed, we delete that file's old chunks and write a new version.
"""

import argparse
import asyncio

from app.rag.ingestion import load_policy_documents, split_documents
from app.rag.lifecycle import bump_version, current_version, replace_source_chunks


def parse_args():
    parser = argparse.ArgumentParser(
        description="Chunk policy markdown and (re)index Atlas.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print chunks and metadata. Do not write to MongoDB.",
    )
    return parser.parse_args()


def print_chunks(chunks):
    print(f"Created {len(chunks)} chunks")
    for index, chunk in enumerate(chunks, start=1):
        meta = chunk.metadata
        print(
            f"  {index:2}. source={meta.get('source')}  "
            f"policy={meta.get('policy')}  "
            f"section={meta.get('section')}  "
            f"active={meta.get('active')}"
        )


async def ingest(dry_run: bool = False):
    documents = load_policy_documents()
    print(f"Loaded {len(documents)} documents")

    if dry_run:
        chunks = split_documents(documents)
        print_chunks(chunks)
        print("Dry run — Atlas was not changed")
        return

    from app.rag.vector_store import vector_store

    for document in documents:
        source = document.metadata["source"]
        digest = document.metadata["content_hash"]
        previous = await current_version(source)
        if previous and previous.get("content_hash") == digest:
            print(f"Unchanged {source} (version {previous.get('version')}) — skip")
            continue

        version = await bump_version(source, digest)
        document.metadata["version"] = version
        chunks = split_documents([document])
        print_chunks(chunks)
        removed = await replace_source_chunks(source, chunks, vector_store)
        print(
            f"Indexed {source} version={version} "
            f"(removed {removed} old chunks)"
        )

    print("Policies indexed successfully")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(ingest(dry_run=args.dry_run))
