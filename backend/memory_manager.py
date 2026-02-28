"""
memory_manager.py — Token-Optimized RAG via ChromaDB
=====================================================
Agents NEVER pass full conversation histories. Instead, they query
a local vector store and retrieve at most 2 chunks capped at ~500 tokens.
"""

import logging
import time
import uuid
from typing import Optional

import chromadb
from chromadb.config import Settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("memory_manager")

_client: Optional[chromadb.ClientAPI] = None
_collection: Optional[chromadb.Collection] = None

COLLECTION_NAME = "x10v_swarm_memory"


def _get_collection() -> chromadb.Collection:
    """Lazily initialise ChromaDB and return the shared collection."""
    global _client, _collection
    if _collection is None:
        logger.info("Initialising local ChromaDB instance …")
        _client = chromadb.Client(Settings(anonymized_telemetry=False))
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "ChromaDB collection '%s' ready  (docs: %d)",
            COLLECTION_NAME,
            _collection.count(),
        )
    return _collection


def log_memory(agent_name: str, action: str) -> str:
    """
    Persist an agent decision into the vector store.

    Returns the generated document id.
    """
    collection = _get_collection()
    doc_id = f"{agent_name}-{uuid.uuid4().hex[:8]}"
    document = f"[{agent_name}] {action}"
    metadata = {
        "agent": agent_name,
        "timestamp": time.time(),
    }
    collection.add(
        ids=[doc_id],
        documents=[document],
        metadatas=[metadata],
    )
    logger.info("Logged memory  ➜  id=%s  doc=%s", doc_id, document[:120])
    return doc_id


def get_relevant_context(query: str, max_tokens: int = 500) -> str:
    """
    Retrieve the **top-2** semantically relevant chunks from memory,
    hard-capped at *max_tokens* (approximated as whitespace-split words).

    This is THE token fix — agents call this instead of forwarding entire
    conversation histories.
    """
    collection = _get_collection()

    if collection.count() == 0:
        logger.info("Memory is empty — returning blank context.")
        return ""

    results = collection.query(
        query_texts=[query],
        n_results=min(2, collection.count()),
    )

    documents = results.get("documents", [[]])[0]
    combined = "\n".join(documents)

    tokens = combined.split()
    if len(tokens) > max_tokens:
        combined = " ".join(tokens[:max_tokens])
        logger.info(
            "Context trimmed from %d to %d tokens for query: '%s'",
            len(tokens),
            max_tokens,
            query[:80],
        )
    else:
        logger.info(
            "Context retrieved: %d tokens for query: '%s'",
            len(tokens),
            query[:80],
        )

    return combined


def clear_memory() -> int:
    """Wipe all documents (useful for testing). Returns count deleted."""
    global _collection
    _collection = None          # force re-creation
    _client_local = chromadb.Client(Settings(anonymized_telemetry=False))
    try:
        _client_local.delete_collection(COLLECTION_NAME)
        logger.info("Memory cleared.")
    except Exception:
        pass
    return 0
