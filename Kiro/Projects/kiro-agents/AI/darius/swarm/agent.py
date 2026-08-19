"""
SwarmAgent — An ephemeral execution unit in the Darius Agent Swarm.

Unlike Docker container agents (fixed skill, always running), a SwarmAgent is:
- Instantiated on the fly for a specific sub-task
- Given a dynamically composed skill prompt
- Assigned a model tier based on task complexity
- Connected to shared memory for cross-agent coordination

Lifecycle: instantiate → run → write results → terminate
"""
import os
import time
import logging
from litellm import completion

from AI.darius.swarm.memory import SharedMemory

logger = logging.getLogger("darius.swarm.agent")

_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Model tiers for agents
MODELS = {
    "apex": os.environ.get("DARIUS_MODEL_APEX", "anthropic/claude-opus-4-6"),
    "heavy": os.environ.get("DARIUS_MODEL_HEAVY", "anthropic/claude-sonnet-5"),
    "default": os.environ.get("DARIUS_MODEL", "anthropic/claude-sonnet-4-6"),
    "light": os.environ.get("DARIUS_MODEL_LIGHT", "anthropic/claude-haiku-4-5-20251001"),
    "creative": os.environ.get("DARIUS_MODEL_CREATIVE", "anthropic/claude-fable-5"),
}

_COSTS = {
    "apex": {"input": 15.0, "output": 75.0},
    "heavy": {"input": 3.0, "output": 15.0},
    "default": {"input": 3.0, "output": 15.0},
    "light": {"input": 0.25, "output": 1.25},
    "creative": {"input": 3.0, "output": 15.0},
}


class SwarmAgent:
    """
    A single ephemeral agent in the swarm.

    Reads from shared memory, executes its task, writes results back.
    Can read other agents' results via shared memory for coordination.
    """

    def __init__(
        self,
        agent_id: str,
        role: str,
        task: str,
        skill_prompt: str,
        model_tier: str = "default",
        memory: SharedMemory = None,
    ):
        self.agent_id = agent_id
        self.role = role
        self.task = task
        self.skill_prompt = skill_prompt
        self.model_tier = model_tier
        self.model = MODELS.get(model_tier, MODELS["default"])
        self.memory = memory
        self.result = None
        self.summary = None
        self.status = "pending"
        self.latency_ms = 0
        self.tokens_in = 0
        self.tokens_out = 0

    def run(self) -> str:
        """Execute this agent's task. Reads shared memory, produces result."""
        self.status = "running"
        if self.memory:
            self.memory.set(f"agent:{self.agent_id}:status", "running")

        start = time.time()

        # Build context from shared memory (what other agents have done)
        peer_context = self._read_peer_context()

        # Compose the full prompt
        messages = [
            {"role": "system", "content": self.skill_prompt},
            {"role": "user", "content": self._build_prompt(peer_context)},
        ]

        # Execute
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "api_key": _API_KEY,
                "max_tokens": 4096,
            }
            if "sonnet-5" not in self.model and "opus-4-7" not in self.model:
                kwargs["temperature"] = 0.2

            response = completion(**kwargs)

            self.result = response.choices[0].message.content.strip()
            self.tokens_in = response.usage.prompt_tokens if response.usage else 0
            self.tokens_out = response.usage.completion_tokens if response.usage else 0
            self.status = "complete"

        except Exception as e:
            self.result = f"ERROR: {e}"
            self.status = "failed"
            logger.error(f"[{self.agent_id}] Failed: {e}")

        self.latency_ms = int((time.time() - start) * 1000)

        # Compress result for other agents to read
        self.summary = self._compress(self.result)

        # Write to shared memory
        if self.memory:
            self.memory.set(f"agent:{self.agent_id}:status", self.status)
            self.memory.set(f"agent:{self.agent_id}:result", self.result[:30000])
            self.memory.set(f"agent:{self.agent_id}:summary", self.summary)
            self.memory.set(f"agent:{self.agent_id}:role", self.role)

            # Track tokens at the swarm level
            rate = _COSTS.get(self.model_tier, _COSTS["default"])
            cost = (self.tokens_in * rate["input"] / 1_000_000) + (self.tokens_out * rate["output"] / 1_000_000)
            self.memory.track_tokens(self.tokens_in, self.tokens_out, cost)

        logger.info(f"[{self.agent_id}] {self.status} in {self.latency_ms}ms ({self.tokens_in}+{self.tokens_out} tokens)")
        return self.result

    def _read_peer_context(self) -> str:
        """Read summaries from other agents that have already completed."""
        if not self.memory:
            return ""

        # Get all agent IDs from shared memory
        agents = self.memory.get("active_agents", [])
        peer_summaries = []

        for aid in agents:
            if aid == self.agent_id:
                continue
            status = self.memory.get(f"agent:{aid}:status")
            if status == "complete":
                role = self.memory.get(f"agent:{aid}:role", "agent")
                summary = self.memory.get(f"agent:{aid}:summary", "")
                if summary:
                    peer_summaries.append(f"[{role}]: {summary}")

        if not peer_summaries:
            return ""
        return "\n".join(peer_summaries)

    def _build_prompt(self, peer_context: str) -> str:
        """Build the execution prompt with peer context."""
        parts = []

        if peer_context:
            parts.append(f"[Context from other agents in this task]\n{peer_context}")

        parts.append(f"[Your Task]\n{self.task}")

        return "\n\n".join(parts)

    def _compress(self, result: str) -> str:
        """Compress result to a brief summary for other agents to consume."""
        if not result or len(result) < 200:
            return result or ""

        try:
            response = completion(
                model=MODELS["light"],
                messages=[
                    {"role": "user", "content": f"Summarize in 2-3 sentences. Be specific about what was produced:\n\n{result[:3000]}"}
                ],
                api_key=_API_KEY,
                max_tokens=150,
                temperature=0.1,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return result[:300] + "..."

    def to_dict(self) -> dict:
        """Serialize agent state for reporting."""
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "model_tier": self.model_tier,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "summary": self.summary,
        }
