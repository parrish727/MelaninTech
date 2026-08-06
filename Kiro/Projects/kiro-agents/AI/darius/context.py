"""
Darius Context Manager — compressed context and smart retrieval.

Architecture (post-Qdrant migration):
  - Context summaries: Qdrant primary (context_summaries collection), pgvector fallback
  - Cross-session memory: Qdrant primary (task_memory collection), pgvector fallback
  - Recent turns: still from darius_sessions table (no semantic search needed)

Strategy:
  - Every 5 turns, compress the conversation into a summary (using light model)
  - Store summaries with embeddings for semantic retrieval
  - When building context for a new task:
    1. Last 3 raw turns (recent context)
    2. Top 3 relevant summaries (deep memory) — via Qdrant
    3. Top 2 relevant past task_memory results (cross-session learning) — via Qdrant

Token budget: ~4000 tokens for context, leaving the rest for task + output.
"""
import os
import hashlib
import logging
from litellm import completion

logger = logging.getLogger("darius.context")

_MODEL_COMPRESS = os.environ.get("DARIUS_MODEL_COMPRESS", "anthropic/claude-haiku-4-5-20251001")
_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
_CONTEXT_CACHE_TTL = 120  # 2 minutes — context changes with new turns

# How many turns between compressions
_COMPRESS_INTERVAL = 5

# Token budget for context (approximate — 4 chars per token)
_CONTEXT_TOKEN_BUDGET = 4000
_CHARS_PER_TOKEN = 4
_CONTEXT_CHAR_BUDGET = _CONTEXT_TOKEN_BUDGET * _CHARS_PER_TOKEN

COMPRESSION_PROMPT = """Summarize this conversation segment into a concise paragraph.
Capture: key decisions made, files modified, technical context, and any unresolved items.
Be specific about file paths, function names, and architectural choices.
Output ONLY the summary paragraph — no headers, no bullets, no formatting."""

# ── Redis Context Cache ───────────────────────────────────────────────────────
_redis_conn = None


def _get_redis():
    global _redis_conn
    if _redis_conn is None:
        try:
            import redis
            _redis_conn = redis.Redis.from_url(_REDIS_URL, decode_responses=True, socket_connect_timeout=2)
            _redis_conn.ping()
        except Exception:
            _redis_conn = None
    return _redis_conn


# ── Qdrant (Primary) ─────────────────────────────────────────────────────────

_semantic_layer = None


def _get_qdrant():
    """Lazy-init the Qdrant SemanticLayer client."""
    global _semantic_layer
    if _semantic_layer is None:
        try:
            from integrations.qdrant_client import SemanticLayer
            _semantic_layer = SemanticLayer()
            if not _semantic_layer.health():
                logger.warning("Qdrant not healthy — context will use pgvector fallback")
                _semantic_layer = None
        except Exception as e:
            logger.warning(f"Qdrant init failed: {e} — using pgvector fallback")
            _semantic_layer = None
    return _semantic_layer


# ── Helpers ───────────────────────────────────────────────────────────────────

def _context_cache_key(session_id: str, task: str) -> str:
    """Cache key for build_context results."""
    task_hash = hashlib.sha256(task.encode()).hexdigest()[:12]
    return f"darius:ctx:{session_id}:{task_hash}"


def _recall_summaries_qdrant(session_id: str, query: str, limit: int = 3) -> list[dict]:
    """Retrieve context summaries from Qdrant with session_id filter."""
    sl = _get_qdrant()
    if not sl:
        return []

    results = sl.search_with_filter(
        "context_summaries",
        query=query,
        must=[{"key": "session_id", "match": {"value": session_id}}],
        limit=limit,
    )
    return [
        {
            "summary": r["payload"].get("summary", r["payload"].get("_text", "")),
            "turn_start": r["payload"].get("turn_start", 0),
            "turn_end": r["payload"].get("turn_end", 0),
        }
        for r in results
    ]


def _recall_cross_session_qdrant(task: str, limit: int = 2) -> list[dict]:
    """Retrieve cross-session task memory from Qdrant."""
    sl = _get_qdrant()
    if not sl:
        return []

    results = sl.search("task_memory", query=task, limit=limit)
    return [
        {
            "task": r["payload"].get("task", ""),
            "agent": r["payload"].get("agent", ""),
            "decision": r["payload"].get("decision", ""),
        }
        for r in results
    ]


def _recall_business_context(query: str, project: str = "default", limit: int = 3) -> list[dict]:
    """
    Retrieve relevant business/LOB documentation from Qdrant business_context.
    Scoped by LOB when project matches a known LOB, otherwise searches globally.
    """
    sl = _get_qdrant()
    if not sl:
        return []

    # Map common project/session IDs to LOB names
    lob_map = {
        "orthoflow": "OrthoFlow",
        "parcelpro": "ParcelPro",
        "artistos": "ArtistOS",
        "htc": "Held Together Caregiving",
        "melanin-core": "MelaninTech Core",
        "default": None,  # Search all LOBs
    }

    lob_name = lob_map.get(project.lower().replace(" ", "").replace("-", ""))

    try:
        if lob_name:
            # LOB-scoped search
            results = sl.search_with_filter(
                "business_context",
                query=query,
                must=[{"key": "lob", "match": {"value": lob_name}}],
                limit=limit,
            )
            # If LOB-scoped returns too few results, supplement with global
            if len(results) < 2:
                global_results = sl.search("business_context", query=query, limit=limit)
                # Add non-duplicate global results
                seen_ids = {r["id"] for r in results}
                for gr in global_results:
                    if gr["id"] not in seen_ids and len(results) < limit:
                        results.append(gr)
        else:
            # Global search across all LOBs
            results = sl.search("business_context", query=query, limit=limit)

        return [
            {
                "text": r["payload"].get("_text", "")[:500],
                "source_file": r["payload"].get("source_file", ""),
                "lob": r["payload"].get("lob", ""),
            }
            for r in results
            if r.get("score", 0) > 0.4  # Only include reasonably relevant results
        ]
    except Exception as e:
        logger.debug(f"Business context search failed: {e}")
        return []


# ── Compression ───────────────────────────────────────────────────────────────

def maybe_compress(session_id: str):
    """
    Check if the session needs compression and compress if so.
    Called after each turn is saved.
    """
    from AI.darius.memory import (
        get_session_turn_count,
        get_last_summary_turn,
        load_session,
        save_context_summary,
    )

    total_turns = get_session_turn_count(session_id)
    last_summarized = get_last_summary_turn(session_id)
    unsummarized = total_turns - last_summarized

    if unsummarized < _COMPRESS_INTERVAL:
        return  # Not enough new turns

    # Load the unsummarized turns
    all_turns = load_session(session_id)
    turns_to_compress = all_turns[last_summarized:last_summarized + _COMPRESS_INTERVAL]

    if not turns_to_compress:
        return

    # Format turns for compression
    text = "\n".join(
        f"[{t['role']}]: {t['content'][:500]}" for t in turns_to_compress
    )

    # Compress via LLM
    try:
        response = completion(
            model=_MODEL_COMPRESS,
            api_key=_API_KEY,
            messages=[
                {"role": "system", "content": COMPRESSION_PROMPT},
                {"role": "user", "content": text},
            ],
            max_tokens=300,
            temperature=0.0,
        )
        summary = response.choices[0].message.content.strip()

        save_context_summary(
            session_id=session_id,
            summary=summary,
            turn_start=last_summarized + 1,
            turn_end=last_summarized + _COMPRESS_INTERVAL,
        )
        logger.info(f"Compressed turns {last_summarized+1}-{last_summarized+_COMPRESS_INTERVAL} for session {session_id}")

    except Exception as e:
        logger.warning(f"Context compression failed: {e}")


# ── Context Builder ───────────────────────────────────────────────────────────

def build_context(session_id: str, current_task: str) -> str:
    """
    Build an enriched context string for a new task.

    Components (in order):
      1. Relevant compressed summaries from this session (Qdrant primary)
      2. Last 3 raw turns for recency
      3. Relevant past tasks from cross-session memory (Qdrant primary)
      4. Business context from LOB documents (Qdrant business_context, LOB-scoped)

    Uses Redis cache (2-min TTL) to avoid re-embedding and search queries
    on rapid successive calls within the same session.

    Returns a formatted string within the token budget.
    """
    # Check Redis cache first
    r = _get_redis()
    cache_key = _context_cache_key(session_id, current_task)
    if r:
        try:
            cached = r.get(cache_key)
            if cached:
                logger.debug(f"Context cache hit for {session_id}")
                return cached
        except Exception:
            pass

    from AI.darius.memory import load_session, recall_context_summaries

    parts = []
    char_budget = _CONTEXT_CHAR_BUDGET

    # 1. Relevant summaries (deep memory) — Qdrant primary, pgvector fallback
    try:
        summaries = _recall_summaries_qdrant(session_id, current_task, limit=3)

        # Fallback to pgvector if Qdrant returned nothing
        if not summaries:
            summaries = recall_context_summaries(session_id, current_task, limit=3)

        if summaries:
            summary_text = "\n".join(
                f"[Turns {s['turn_start']}-{s['turn_end']}]: {s['summary']}"
                for s in summaries
            )
            header = "=== Session History (compressed) ===\n"
            section = header + summary_text
            if len(section) < char_budget * 0.4:  # max 40% of budget
                parts.append(section)
                char_budget -= len(section)
    except Exception as e:
        logger.warning(f"Failed to retrieve summaries: {e}")

    # 2. Last 3 raw turns (recency) — always from PostgreSQL (no semantic search needed)
    try:
        history = load_session(session_id)
        recent = history[-3:] if len(history) >= 3 else history
        if recent:
            recent_text = "\n".join(
                f"[{t['role']}]: {t['content'][:800]}" for t in recent
            )
            header = "\n=== Recent Turns ===\n"
            section = header + recent_text
            if len(section) < char_budget * 0.4:  # max 40% of budget
                parts.append(section)
                char_budget -= len(section)
    except Exception as e:
        logger.warning(f"Failed to load recent turns: {e}")

    # 3. Cross-session memory (past similar tasks) — Qdrant primary, pgvector fallback
    try:
        past_tasks = _recall_cross_session_qdrant(current_task, limit=2)

        # Fallback to pgvector if Qdrant returned nothing
        if not past_tasks:
            from orchestrator.memory import recall
            past_tasks = recall(current_task, limit=2)

        if past_tasks:
            past_text = "\n".join(
                f"- [{t['decision']}] {t.get('agent', '')}: {t['task'][:200]}"
                for t in past_tasks
            )
            header = "\n=== Related Past Tasks ===\n"
            section = header + past_text
            if len(section) < char_budget:
                parts.append(section)
    except Exception as e:
        # Cross-session memory might not be available
        logger.debug(f"Cross-session recall unavailable: {e}")

    # 4. Business context (LOB documents) — LOB-scoped from Qdrant business_context
    try:
        business_docs = _recall_business_context(current_task, project=session_id, limit=3)
        if business_docs:
            biz_text = "\n".join(
                f"- [{d['source_file']}]: {d['text'][:400]}"
                for d in business_docs
            )
            header = "\n=== Business Context ===\n"
            section = header + biz_text
            if len(section) < char_budget:
                parts.append(section)
                char_budget -= len(section)
    except Exception as e:
        logger.debug(f"Business context retrieval unavailable: {e}")

    if not parts:
        return ""

    result = "\n".join(parts)

    # Cache the assembled context (2-min TTL)
    if r:
        try:
            r.setex(cache_key, _CONTEXT_CACHE_TTL, result)
        except Exception:
            pass

    return result
