"""
ChromaDB Vector Store
---------------------
Handles storing and retrieving document chunks. ChromaDB embeds text
automatically using its default embedding function (all-MiniLM-L6-v2).

Two main operations:
- add_chunks: load chunked documents into the collection
- query: retrieve the most relevant chunks for a user message
"""

import chromadb

COLLECTION_NAME = "maternal_health"

_client = chromadb.PersistentClient(path="data/chroma")
_collection = _client.get_or_create_collection(name=COLLECTION_NAME)


def add_chunks(chunks):
    """
    Add a list of chunks to the collection.

    Each chunk should have 'id', 'text', and 'metadata' keys
    (the format produced by chunker.chunk_document).
    """
    if not chunks:
        return

    _collection.upsert(
        ids=[c['id'] for c in chunks],
        documents=[c['text'] for c in chunks],
        metadatas=[c['metadata'] for c in chunks],
    )


def query(text, n_results=5):
    """
    Query the collection for chunks most relevant to the given text.

    Returns a list of dicts with 'id', 'text', and 'metadata' keys.
    """
    results = _collection.query(
        query_texts=[text],
        n_results=n_results,
    )

    chunks = []
    for i in range(len(results['ids'][0])):
        chunks.append({
            'id': results['ids'][0][i],
            'text': results['documents'][0][i],
            'metadata': results['metadatas'][0][i],
        })

    return chunks
