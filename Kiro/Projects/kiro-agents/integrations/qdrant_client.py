"""
Qdrant Semantic Layer — Unified vector search client for Melanin Technologies.

Replaces pgvector for semantic retrieval. Provides:
- Embedding via Ollama nomic-embed-text (768-dim)
- Collection management (create, upsert, search, delete)
- Typed collections: task_memory, conversation_memory, graph_nodes, context_summaries

Usage:
    from integrations.qdrant_client import SemanticLayer
    sl = SemanticLayer()
    sl.upsert("task_memory", id="task-123", text="...", metadata={...})
    results = sl.search("task_memory", query="fix auth bug", limit=5)
"""
import os
import uuid
import logging
import httpx
from typing import Optional

logger = logging.getLogger("semantic_layer")

QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = "nomic-embed-text"
VECTOR_DIM = 768

# Collection definitions
COLLECTIONS = {
    "task_memory": {
        "description": "Past task decisions and outcomes for semantic recall",
        "payload_fields": ["task", "proposal", "agent", "decision", "project", "created_at"],
    },
    "conversation_memory": {
        "description": "CEO/system conversation turns for persistent context",
        "payload_fields": ["role", "content", "created_at"],
    },
    "graph_nodes": {
        "description": "Knowledge graph nodes for semantic graph search",
        "payload_fields": ["label", "content", "file_type", "community_name", "source_file"],
    },
    "context_summaries": {
        "description": "Compressed session summaries for Darius context retrieval",
        "payload_fields": ["session_id", "summary", "turn_start", "turn_end", "created_at"],
    },
}


class SemanticLayer:
    """Unified interface to Qdrant for all semantic operations."""

    def __init__(self, qdrant_url: str = None, ollama_url: str = None):
        self.qdrant_url = qdrant_url or QDRANT_URL
        self.ollama_url = ollama_url or OLLAMA_URL
        self._client = httpx.Client(timeout=30)

    # ── Embedding ─────────────────────────────────────────────────────────────

    def embed(self, text: str) -> list[float]:
        """Generate embedding via Ollama nomic-embed-text (768-dim)."""
        response = self._client.post(
            f"{self.ollama_url}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text[:2000]},
        )
        response.raise_for_status()
        return response.json()["embedding"]

    # ── Collection Management ─────────────────────────────────────────────────

    def ensure_collections(self):
        """Create all defined collections if they don't exist."""
        for name in COLLECTIONS:
            self._create_collection_if_not_exists(name)
        logger.info(f"All {len(COLLECTIONS)} collections ensured")

    def _create_collection_if_not_exists(self, name: str):
        """Create a collection with proper vector config."""
        # Check if exists
        r = self._client.get(f"{self.qdrant_url}/collections/{name}")
        if r.status_code == 200:
            return  # Already exists

        # Create
        r = self._client.put(
            f"{self.qdrant_url}/collections/{name}",
            json={
                "vectors": {
                    "size": VECTOR_DIM,
                    "distance": "Cosine",
                },
            },
        )
        r.raise_for_status()
        logger.info(f"Created collection: {name}")

    def collection_info(self, name: str) -> dict:
        """Get collection stats."""
        r = self._client.get(f"{self.qdrant_url}/collections/{name}")
        r.raise_for_status()
        return r.json().get("result", {})

    # ── Upsert ────────────────────────────────────────────────────────────────

    def upsert(self, collection: str, id: str, text: str, metadata: dict = None):
        """Embed text and upsert a single point with payload."""
        vector = self.embed(text)
        payload = metadata or {}
        payload["_text"] = text[:5000]  # Store original text for retrieval

        r = self._client.put(
            f"{self.qdrant_url}/collections/{collection}/points",
            json={
                "points": [
                    {
                        "id": self._to_uuid(id),
                        "vector": vector,
                        "payload": payload,
                    }
                ]
            },
        )
        r.raise_for_status()

    def upsert_batch(self, collection: str, points: list[dict]):
        """
        Batch upsert multiple points.
        Each point: {"id": "...", "text": "...", "metadata": {...}}
        """
        qdrant_points = []
        for p in points:
            vector = self.embed(p["text"])
            payload = p.get("metadata", {})
            payload["_text"] = p["text"][:5000]
            qdrant_points.append({
                "id": self._to_uuid(p["id"]),
                "vector": vector,
                "payload": payload,
            })

        # Qdrant supports batch up to ~100 at a time
        batch_size = 64
        for i in range(0, len(qdrant_points), batch_size):
            batch = qdrant_points[i:i + batch_size]
            r = self._client.put(
                f"{self.qdrant_url}/collections/{collection}/points",
                json={"points": batch},
            )
            r.raise_for_status()

        logger.info(f"Upserted {len(points)} points to {collection}")

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, collection: str, query: str, limit: int = 5, filter: dict = None, score_threshold: float = 0.3) -> list[dict]:
        """
        Semantic search — embed query, find nearest neighbors.
        Returns list of {id, score, payload} dicts.
        """
        vector = self.embed(query)

        body = {
            "vector": vector,
            "limit": limit,
            "with_payload": True,
            "score_threshold": score_threshold,
        }
        if filter:
            body["filter"] = filter

        r = self._client.post(
            f"{self.qdrant_url}/collections/{collection}/points/search",
            json=body,
        )
        r.raise_for_status()

        results = []
        for hit in r.json().get("result", []):
            results.append({
                "id": hit.get("id"),
                "score": hit.get("score"),
                "payload": hit.get("payload", {}),
            })

        return results

    def search_with_filter(self, collection: str, query: str, must: list[dict] = None, limit: int = 5) -> list[dict]:
        """
        Search with Qdrant filtering.
        must: [{"key": "agent", "match": {"value": "darius"}}]
        """
        qdrant_filter = None
        if must:
            qdrant_filter = {"must": must}
        return self.search(collection, query, limit=limit, filter=qdrant_filter)

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete(self, collection: str, id: str):
        """Delete a single point by ID."""
        r = self._client.post(
            f"{self.qdrant_url}/collections/{collection}/points/delete",
            json={"points": [self._to_uuid(id)]},
        )
        r.raise_for_status()

    def delete_collection(self, name: str):
        """Delete an entire collection."""
        r = self._client.delete(f"{self.qdrant_url}/collections/{name}")
        r.raise_for_status()
        logger.info(f"Deleted collection: {name}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _to_uuid(id_str: str) -> str:
        """Convert any string ID to a valid UUID for Qdrant."""
        if len(id_str) == 36 and id_str.count("-") == 4:
            return id_str  # Already a UUID
        # Generate deterministic UUID from string
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, id_str))

    def health(self) -> bool:
        """Check Qdrant health."""
        try:
            r = self._client.get(f"{self.qdrant_url}/collections", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def stats(self) -> dict:
        """Get all collection stats."""
        r = self._client.get(f"{self.qdrant_url}/collections")
        r.raise_for_status()
        collections = r.json().get("result", {}).get("collections", [])
        stats = {}
        for c in collections:
            info = self.collection_info(c["name"])
            stats[c["name"]] = {
                "vectors_count": info.get("vectors_count", 0),
                "points_count": info.get("points_count", 0),
                "status": info.get("status", "unknown"),
            }
        return stats
