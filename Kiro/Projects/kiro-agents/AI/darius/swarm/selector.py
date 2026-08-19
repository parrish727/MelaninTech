"""
Adaptive Engine Selector — Learns which execution engine performs best for each task type.

Maintains a performance map:
  task_classification → {engine: score} 

Score = weighted combination of:
  - Success rate (40%)
  - Token efficiency (30%)
  - Latency (20%)
  - Cost (10%)

When a new task comes in, classify it and route to the best-performing engine
based on historical data. Falls back to 'delta' if no data available.
"""
import os
import json
import hashlib
import logging

logger = logging.getLogger("darius.swarm.selector")

_DSN = os.environ.get("POSTGRES_DSN", "")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

# Task classification keywords
TASK_CLASSIFICATIONS = {
    "multi_domain": ["frontend and backend", "full stack", "end to end", "three things", "parallel"],
    "architecture": ["architect", "redesign", "system design", "migration strategy"],
    "implementation": ["implement", "build", "create", "write code", "add feature"],
    "debugging": ["fix", "debug", "broken", "error", "crash", "not working"],
    "analysis": ["analyze", "review", "audit", "assess", "evaluate"],
    "documentation": ["write docs", "documentation", "readme", "proposal", "report"],
    "deployment": ["deploy", "docker", "container", "release", "launch"],
    "simple": ["rename", "move", "delete", "list", "check", "status", "what is"],
}

# Engine options
ENGINES = ["smolagents", "delta", "swarm"]


def classify_task(task: str) -> str:
    """Classify a task into one of the known categories."""
    t = task.lower()
    for classification, keywords in TASK_CLASSIFICATIONS.items():
        if any(k in t for k in keywords):
            return classification
    return "general"


def select_engine(task: str) -> str:
    """
    Select the best engine for a task based on historical performance.
    Returns: "smolagents", "delta", or "swarm"
    """
    classification = classify_task(task)

    # Check Redis cache for performance data
    performance = _get_performance_data(classification)

    if not performance:
        # No historical data — use heuristics
        return _heuristic_select(classification)

    # Score each engine
    best_engine = "delta"
    best_score = -1

    for engine, stats in performance.items():
        if stats.get("executions", 0) < 2:
            continue  # Not enough data

        score = (
            stats.get("success_rate", 0) * 0.4 +
            stats.get("token_efficiency", 50) * 0.3 +
            stats.get("speed_score", 50) * 0.2 +
            stats.get("cost_score", 50) * 0.1
        )

        if score > best_score:
            best_score = score
            best_engine = engine

    logger.info(f"Task classified as '{classification}' → engine '{best_engine}' (score: {best_score:.1f})")
    return best_engine


def _heuristic_select(classification: str) -> str:
    """Rule-based fallback when no performance data exists."""
    heuristics = {
        "multi_domain": "swarm",      # Parallel agents shine here
        "architecture": "delta",       # Sequential deep thinking
        "implementation": "delta",     # Step-by-step implementation
        "debugging": "smolagents",     # Needs tool access (file read/write)
        "analysis": "delta",           # Sequential analysis
        "documentation": "delta",      # Sequential writing
        "deployment": "smolagents",    # Needs shell/docker tools
        "simple": "delta",             # Single step, fast
        "general": "delta",            # Default: token-efficient
    }
    return heuristics.get(classification, "delta")


def record_execution(task: str, engine: str, success: bool, tokens: int, latency_ms: int, cost: float):
    """
    Record an execution result for future engine selection.
    Called after every task completion.
    """
    classification = classify_task(task)

    try:
        import redis
        r = redis.Redis.from_url(_REDIS_URL, decode_responses=True, socket_connect_timeout=2)

        key = f"engine_perf:{classification}:{engine}"
        current = r.get(key)
        if current:
            stats = json.loads(current)
        else:
            stats = {"executions": 0, "successes": 0, "total_tokens": 0, "total_latency": 0, "total_cost": 0}

        stats["executions"] += 1
        if success:
            stats["successes"] += 1
        stats["total_tokens"] += tokens
        stats["total_latency"] += latency_ms
        stats["total_cost"] += cost

        # Compute normalized scores (0-100)
        stats["success_rate"] = (stats["successes"] / max(stats["executions"], 1)) * 100
        avg_tokens = stats["total_tokens"] / max(stats["executions"], 1)
        avg_latency = stats["total_latency"] / max(stats["executions"], 1)

        # Token efficiency: lower is better, normalize against 50K baseline
        stats["token_efficiency"] = max(0, min(100, (1 - avg_tokens / 50000) * 100))
        # Speed: lower latency is better, normalize against 120s baseline
        stats["speed_score"] = max(0, min(100, (1 - avg_latency / 120000) * 100))
        # Cost: lower is better, normalize against $0.50 baseline
        avg_cost = stats["total_cost"] / max(stats["executions"], 1)
        stats["cost_score"] = max(0, min(100, (1 - avg_cost / 0.50) * 100))

        r.setex(key, 604800, json.dumps(stats))  # 7 day TTL

    except Exception as e:
        logger.debug(f"Failed to record execution: {e}")


def _get_performance_data(classification: str) -> dict:
    """Get historical performance for all engines on this task type."""
    try:
        import redis
        r = redis.Redis.from_url(_REDIS_URL, decode_responses=True, socket_connect_timeout=2)

        performance = {}
        for engine in ENGINES:
            key = f"engine_perf:{classification}:{engine}"
            data = r.get(key)
            if data:
                performance[engine] = json.loads(data)

        return performance

    except Exception:
        return {}


def get_all_performance() -> dict:
    """Get full performance map for reporting/observability."""
    try:
        import redis
        r = redis.Redis.from_url(_REDIS_URL, decode_responses=True, socket_connect_timeout=2)

        all_data = {}
        for classification in TASK_CLASSIFICATIONS:
            all_data[classification] = {}
            for engine in ENGINES:
                key = f"engine_perf:{classification}:{engine}"
                data = r.get(key)
                if data:
                    all_data[classification][engine] = json.loads(data)

        return all_data

    except Exception:
        return {}
