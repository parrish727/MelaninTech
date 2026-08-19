"""
SharedMemory — Redis-backed state layer for the DeltaExecutor and future Agent Swarm.

Schema:
  swarm:{task_id}:plan              → JSON execution plan
  swarm:{task_id}:steps             → LIST of completed step summaries
  swarm:{task_id}:step:{n}:result   → full result text for step n
  swarm:{task_id}:step:{n}:summary  → compressed summary (~200 tokens)
  swarm:{task_id}:step:{n}:files    → LIST of files modified in step n
  swarm:{task_id}:status            → "running" | "complete" | "failed"
  swarm:{task_id}:token_usage       → JSON {input: N, output: N, cost: $}

All keys expire after 1 hour (configurable via TTL).
"""
import os
import json
import time
import logging
from typing import Any

logger = logging.getLogger("darius.swarm.memory")

_REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
_TTL = int(os.environ.get("SWARM_MEMORY_TTL", "3600"))  # 1 hour default

_redis = None


def _get_redis():
    global _redis
    if _redis is None:
        try:
            import redis
            _redis = redis.Redis.from_url(_REDIS_URL, decode_responses=True, socket_connect_timeout=3)
            _redis.ping()
        except Exception as e:
            logger.warning(f"Redis unavailable for SharedMemory: {e}")
            _redis = None
    return _redis


class SharedMemory:
    """
    Redis-backed shared memory for a single task execution.
    All operations are atomic and TTL-managed.
    """

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.prefix = f"swarm:{task_id}"
        self.r = _get_redis()

    def _key(self, suffix: str) -> str:
        return f"{self.prefix}:{suffix}"

    # ── Core State ────────────────────────────────────────────────────────────

    def set(self, key: str, value: Any):
        """Set a value (auto-serializes dicts/lists to JSON)."""
        if not self.r:
            return
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        self.r.setex(self._key(key), _TTL, value)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value (auto-deserializes JSON strings)."""
        if not self.r:
            return default
        val = self.r.get(self._key(key))
        if val is None:
            return default
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val

    # ── Step Management ───────────────────────────────────────────────────────

    def save_step(self, step_index: int, summary: str, full_result: str, files: list[str] = None):
        """Save a completed step's results."""
        if not self.r:
            return
        pipe = self.r.pipeline()
        pipe.setex(self._key(f"step:{step_index}:summary"), _TTL, summary)
        pipe.setex(self._key(f"step:{step_index}:result"), _TTL, full_result[:50000])
        if files:
            pipe.setex(self._key(f"step:{step_index}:files"), _TTL, json.dumps(files))
        # Append summary to the steps list
        pipe.rpush(self._key("steps"), summary)
        pipe.expire(self._key("steps"), _TTL)
        pipe.execute()

    def get_delta(self, max_summaries: int = 3) -> str:
        """
        Get the delta context for the next step.
        Returns the last N step summaries concatenated — NOT full results.
        This is the core of the token savings.
        """
        if not self.r:
            return ""
        summaries = self.r.lrange(self._key("steps"), -max_summaries, -1)
        if not summaries:
            return ""
        return "\n".join(f"[Step {i+1}]: {s}" for i, s in enumerate(summaries))

    def get_all_summaries(self) -> list[str]:
        """Get all step summaries in order."""
        if not self.r:
            return []
        return self.r.lrange(self._key("steps"), 0, -1) or []

    def get_step_result(self, step_index: int) -> str:
        """Get the full result for a specific step (for when summary isn't enough)."""
        if not self.r:
            return ""
        return self.r.get(self._key(f"step:{step_index}:result")) or ""

    def step_count(self) -> int:
        """How many steps have completed."""
        if not self.r:
            return 0
        return self.r.llen(self._key("steps")) or 0

    # ── Token Tracking ────────────────────────────────────────────────────────

    def track_tokens(self, input_tokens: int, output_tokens: int, cost: float):
        """Accumulate token usage for this task."""
        if not self.r:
            return
        current = self.get("token_usage", {"input": 0, "output": 0, "cost": 0.0})
        current["input"] += input_tokens
        current["output"] += output_tokens
        current["cost"] += cost
        self.set("token_usage", current)

    def get_token_usage(self) -> dict:
        """Get total token usage for this task."""
        return self.get("token_usage", {"input": 0, "output": 0, "cost": 0.0})

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def set_status(self, status: str):
        """Set task status: running, complete, failed."""
        self.set("status", status)

    # ── Cross-Agent Coordination ──────────────────────────────────────────────

    def signal(self, agent_id: str, event: str, data: str = ""):
        """Emit a coordination signal for other agents to observe."""
        if not self.r:
            return
        signal_entry = json.dumps({"agent": agent_id, "event": event, "data": data, "ts": int(time.time())})
        self.r.rpush(self._key("signals"), signal_entry)
        self.r.expire(self._key("signals"), _TTL)

    def get_signals(self, since_index: int = 0) -> list[dict]:
        """Read signals from the coordination queue."""
        if not self.r:
            return []
        raw = self.r.lrange(self._key("signals"), since_index, -1)
        signals = []
        for entry in (raw or []):
            try:
                signals.append(json.loads(entry))
            except json.JSONDecodeError:
                continue
        return signals

    def wait_for_signal(self, event: str, timeout: int = 60) -> bool:
        """Block until a specific signal appears (polling-based)."""
        import time as _time
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            signals = self.get_signals()
            if any(s.get("event") == event for s in signals):
                return True
            _time.sleep(1)
        return False

    # ── Conflict Detection ────────────────────────────────────────────────────

    def declare_file(self, agent_id: str, filepath: str):
        """Declare that an agent intends to modify a file. Used for conflict detection."""
        if not self.r:
            return
        existing = self.get(f"file_lock:{filepath}")
        if existing and existing != agent_id:
            # Conflict detected
            self.r.rpush(self._key("conflicts"), json.dumps({
                "file": filepath,
                "agents": [existing, agent_id],
                "ts": int(time.time()),
            }))
            self.r.expire(self._key("conflicts"), _TTL)
            return False  # Conflict
        self.set(f"file_lock:{filepath}", agent_id)
        return True  # No conflict

    def get_conflicts(self) -> list[dict]:
        """Get all detected file conflicts."""
        if not self.r:
            return []
        raw = self.r.lrange(self._key("conflicts"), 0, -1)
        conflicts = []
        for entry in (raw or []):
            try:
                conflicts.append(json.loads(entry))
            except json.JSONDecodeError:
                continue
        return conflicts

    # ── Cross-Agent Reading ───────────────────────────────────────────────────

    def read_agent_summary(self, agent_id: str) -> str:
        """Read another agent's compressed summary."""
        return self.get(f"agent:{agent_id}:summary", "")

    def read_agent_result(self, agent_id: str) -> str:
        """Read another agent's full result (use sparingly — large)."""
        return self.get(f"agent:{agent_id}:result", "")

    def get_agent_status(self, agent_id: str) -> str:
        """Check if another agent has completed."""
        return self.get(f"agent:{agent_id}:status", "unknown")

    def list_completed_agents(self) -> list[str]:
        """Get IDs of all agents that have completed."""
        agents = self.get("active_agents", [])
        return [a for a in agents if self.get(f"agent:{a}:status") == "complete"]

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def cleanup(self):
        """Explicitly remove all keys for this task (normally TTL handles this)."""
        if not self.r:
            return
        keys = self.r.keys(f"{self.prefix}:*")
        if keys:
            self.r.delete(*keys)
