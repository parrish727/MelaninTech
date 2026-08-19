
import ollama
import psycopg2
import numpy as np
from typing import Optional

OLLAMA_MODEL = "nomic-embed-text"
VECTOR_DIM = 768


def generate_embedding(text: str) -> list[float]:
    """
    Generate a vector embedding from text using Ollama nomic-embed-text.
    nomic-embed-text supports up to 8192 tokens context window.
    """
    response = ollama.embeddings(model=OLLAMA_MODEL, prompt=text)
    return response["embedding"]


def store_embedding(
    conn: psycopg2.extensions.connection,
    content_id: int,
    text: str,
    embedding: list[float],
    table: str = "content_embeddings",
) -> None:
    """
    Store a text and its embedding vector into pgvector-enabled PostgreSQL table.
    """
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {table} (content_id, content_text, embedding)
            VALUES (%s, %s, %s::vector)
            ON CONFLICT (content_id) DO UPDATE
                SET content_text = EXCLUDED.content_text,
                    embedding = EXCLUDED.embedding;
            """,
            (content_id, text, embedding),
        )
    conn.commit()


def cosine_similarity_search(
    conn: psycopg2.extensions.connection,
    query_text: str,
    top_k: int = 10,
    table: str = "content_embeddings",
    similarity_threshold: Optional[float] = 0.7,
) -> list[dict]:
    """
    Perform cosine similarity (ANN) search using pgvector's <=> operator.
    Returns top_k most semantically similar results above the threshold.

    Pipeline:
        text input → nomic-embed-text (Ollama) → float[] vector
                   → pgvector (PostgreSQL) → cosine similarity search
    """
    query_embedding = generate_embedding(query_text)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                content_id,
                content_text,
                1 - (embedding <=> %s::vector) AS similarity
            FROM {table}
            WHERE 1 - (embedding <=> %s::vector) >= %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
            """,
            (query_embedding, query_embedding, similarity_threshold, query_embedding, top_k),
        )
        rows = cur.fetchall()

    return [
        {
            "content_id": row[0],
            "content_text": row[1],
            "similarity": float(row[2]),
        }
        for row in rows
    ]


def embed_and_store(
    conn: psycopg2.extensions.connection,
    content_id: int,
    text: str,
) -> list[float]:
    """
    Convenience wrapper: generate embedding and store in one call.
    Returns the generated embedding vector.
    """
    embedding = generate_embedding(text)
    store_embedding(conn, content_id, text, embedding)
    return embedding