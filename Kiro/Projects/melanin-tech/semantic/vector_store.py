
import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from typing import Generator

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/melanin_tech",
)


@contextmanager
def get_db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Context manager for PostgreSQL connections with pgvector support.
    Registers the vector type adapter for psycopg2 float[] compatibility.
    """
    conn = psycopg2.connect(DATABASE_URL)
    psycopg2.extras.register_default_jsonb(conn)

    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class VectorStore:
    """
    Thin wrapper around pgvector storage and cosine similarity search.

    Semantic layer architecture:
        text input
            → nomic-embed-text via Ollama (local, zero API cost, 8192 token ctx)
            → float[] vector (dim=768)
            → pgvector PostgreSQL 16 extension
            → cosine similarity ANN search (HNSW index)
    """

    def __init__(self, table: str = "content_embeddings"):
        self.table = table

    def upsert(self, content_id: int, text: str) -> list[float]:
        from semantic.embedding_pipeline import embed_and_store

        with get_db_connection() as conn:
            return embed_and_store(conn, content_id, text)

    def search(
        self,
        query: str,
        top_k: int = 10,
        similarity_threshold: float = 0.7,
    ) -> list[dict]:
        from semantic.embedding_pipeline import cosine_similarity_search

        with get_db_connection() as conn:
            return cosine_similarity_search(
                conn,
                query_text=query,
                top_k=top_k,
                table=self.table,
                similarity_threshold=similarity_threshold,
            )

    def delete(self, content_id: int) -> None:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {self.table} WHERE content_id = %s;",
                    (content_id,),
                )
            conn.commit()

    def count(self) -> int:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {self.table};")
                result = cur.fetchone()
                return result[0] if result else 0