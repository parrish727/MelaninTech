
import pytest
from unittest.mock import MagicMock, patch
from semantic.embedding_pipeline import (
    generate_embedding,
    store_embedding,
    cosine_similarity_search,
    embed_and_store,
)

MOCK_EMBEDDING = [0.1] * 768
MOCK_TEXT = "melanin tech community event 2024"
MOCK_CONTENT_ID = 42


@patch("semantic.embedding_pipeline.ollama.embeddings")
def test_generate_embedding_returns_vector(mock_ollama):
    mock_ollama.return_value = {"embedding": MOCK_EMBEDDING}
    result = generate_embedding(MOCK_TEXT)
    assert result == MOCK_EMBEDDING
    mock_ollama.assert_called_once_with(model="nomic-embed-text", prompt=MOCK_TEXT)


@patch("semantic.embedding_pipeline.ollama.embeddings")
def test_generate_embedding_correct_dimension(mock_ollama):
    mock_ollama.return_value = {"embedding": MOCK_EMBEDDING}
    result = generate_embedding(MOCK_TEXT)
    assert len(result) == 768


def test_store_embedding_executes_upsert():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    store_embedding(mock_conn, MOCK_CONTENT_ID, MOCK_TEXT, MOCK_EMBEDDING)

    mock_cursor.execute.assert_called_once()
    sql_call = mock_cursor.execute.call_args[0][0]
    assert "INSERT INTO content_embeddings" in sql_call
    assert "ON CONFLICT (content_id) DO UPDATE" in sql_call
    mock_conn.commit.assert_called_once()


@patch("semantic.embedding_pipeline.ollama.embeddings")
def test_cosine_similarity_search_returns_structured_results(mock_ollama):
    mock_ollama.return_value = {"embedding": MOCK_EMBEDDING}

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchall.return_value = [
        (1, "black tech entrepreneurs summit", 0.92),
        (2, "melanin coders hackathon", 0.85),
    ]

    results = cosine_similarity_search(mock_conn, query_text=MOCK_TEXT, top_k=5)

    assert len(results) == 2
    assert results[0]["content_id"] == 1
    assert results[0]["similarity"] == pytest.approx(0.92)
    assert "content_text" in results[0]


@patch("semantic.embedding_pipeline.store_embedding")
@patch("semantic.embedding_pipeline.generate_embedding")
def test_embed_and_store_calls_both(mock_generate, mock_store):
    mock_generate.return_value = MOCK_EMBEDDING
    mock_conn = MagicMock()

    result = embed_and_store(mock_conn, MOCK_CONTENT_ID, MOCK_TEXT)

    mock_generate.assert_called_once_with(MOCK_TEXT)
    mock_store.assert_called_once_with(mock_conn, MOCK_CONTENT_ID, MOCK_TEXT, MOCK_EMBEDDING)
    assert result == MOCK_EMBEDDING