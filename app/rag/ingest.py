"""
Document Ingestion Script
-------------------------
Reads .txt files from the documents directory, chunks them,
and loads them into ChromaDB.

Usage:
    python -m app.rag.ingest
"""

from pathlib import Path

from app.rag.chunker import chunk_document
from app.rag.store import add_chunks

DOCS_DIR = Path("maternal_health_docs")


def ingest():
    """Process all .txt files and load into the vector store."""
    txt_files = sorted(DOCS_DIR.glob("*.txt"))

    if not txt_files:
        print(f"No .txt files found in {DOCS_DIR}")
        return

    print(f"Found {len(txt_files)} documents\n")

    total_chunks = 0

    for filepath in txt_files:
        print(f"Processing: {filepath.name}")
        chunks = chunk_document(str(filepath))
        add_chunks(chunks)
        total_chunks += len(chunks)
        print(f"  → {len(chunks)} chunks loaded")

    print(f"\nDone. {total_chunks} total chunks in the store.")


if __name__ == "__main__":
    ingest()
