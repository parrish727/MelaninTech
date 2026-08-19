"""
AgentSwarm — Dynamic multi-agent coordinator for complex tasks.

Decomposes a task into parallel sub-tasks, instantiates specialist SwarmAgents
on the fly with dynamically generated skill prompts, runs them in parallel waves,
and synthesizes the combined output.

Unlike the old DAG executor:
- Agents are NOT pre-defined containers
- Skill prompts are generated per-task (not loaded from fixed files)
- Agents share memory and can read each other's partial results
- Parallel execution is real (ThreadPoolExecutor)
- The coordinator can replan mid-execution
"""
import os
import json
import time
import uuid
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from litellm import completion

from AI.darius.swarm.memory import SharedMemory
from AI.darius.swarm.agent import SwarmAgent

logger = logging.getLogger("darius.swarm.coordinator")

_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
_MODEL_COORDINATOR = os.environ.get("DARIUS_MODEL_HEAVY", "anthropic/claude-sonnet-5")
_MODEL_LIGHT = os.environ.get("DARIUS_MODEL_LIGHT", "anthropic/claude-haiku-4-5-20251001")
_MAX_WORKERS = int(os.environ.get("SWARM_MAX_WORKERS", "4"))

DECOMPOSITION_PROMPT = """You are a task coordinator. Decompose the user's task into parallel sub-tasks that can be assigned to specialist agents.

For each sub-agent, specify:
- role: a short name for the specialist (e.g., "backend-engineer", "security-reviewer", "docs-writer")
- task: the specific deliverable this agent must produce
- model_tier: "apex" (architecture/design), "heavy" (implementation), "default" (standard), "light" (analysis), "creative" (docs/narrative)
- depends_on: list of role names this agent must wait for (empty = can run immediately)
- skill_context: 1-2 sentences describing this agent's expertise and constraints

Rules:
- Maximum 6 agents per swarm
- Minimize dependencies — prefer parallel execution
- Each agent should have a clear, verifiable deliverable
- Assign model_tier based on complexity (don't waste Opus on simple tasks)
- Creative/docs tasks should use "creative" tier

Output ONLY this JSON:
{
  "agents": [
    {"role": "...", "task": "...", "model_tier": "...", "depends_on": [], "skill_context": "..."}
  ]
}"""


class AgentSwarm:
    """
    Coordinates multiple SwarmAgents for complex multi-domain tasks.
    """

    def __init__(self, task_id: str = None):
        self.task_id = task_id or f"swarm-{uuid.uuid4().hex[:8]}"
        self.memory = SharedMemory(self.task_id)
        self.agents: list[SwarmAgent] = []
        self.memory.set_status("running")

    def execute(self, task: str, context: str = "") -> dict:
        """
        Full swarm execution:
        1. Decompose task into agent assignments
        2. Instantiate agents with dynamic skills
        3. Execute in parallel waves (respecting dependencies)
        4. Synthesize final output
        """
        start_time = time.time()

        # 1. Decompose
        decomposition = self._decompose(task, context)
        agent_specs = decomposition.get("agents", [])
        logger.info(f"[{self.task_id}] Decomposed into {len(agent_specs)} agents")

        if not agent_specs:
            # Fallback: single agent
            agent_specs = [{"role": "generalist", "task": task, "model_tier": "default", "depends_on": [], "skill_context": "General purpose coding agent."}]

        # 2. Instantiate agents
        self._instantiate_agents(agent_specs)
        self.memory.set("active_agents", [a.agent_id for a in self.agents])
        self.memory.set("plan", [{"role": s["role"], "task": s["task"][:200]} for s in agent_specs])

        # 3. Execute in waves
        waves = self._build_execution_waves(agent_specs)
        for wave_idx, wave in enumerate(waves):
            logger.info(f"[{self.task_id}] Wave {wave_idx+1}/{len(waves)}: {[a.role for a in wave]}")
            self._execute_wave(wave)

        # 4. Synthesize
        final_output = self._synthesize(task)
        total_latency = int((time.time() - start_time) * 1000)
        token_usage = self.memory.get_token_usage()
        self.memory.set_status("complete")

        # Log trace
        self._log_trace(task, token_usage, total_latency)

        return {
            "task_id": self.task_id,
            "engine": "swarm",
            "agents": [a.to_dict() for a in self.agents],
            "final_output": final_output,
            "token_usage": token_usage,
            "latency_ms": total_latency,
            "agent_count": len(self.agents),
            "wave_count": len(waves),
        }

    def _decompose(self, task: str, context: str) -> dict:
        """Use the coordinator model to decompose the task."""
        prompt = f"Task: {task}"
        if context:
            prompt = f"Context:\n{context[:2000]}\n\nTask: {task}"

        try:
            # Some newer models (Sonnet 5) don't accept temperature
            kwargs = {
                "model": _MODEL_COORDINATOR,
                "messages": [
                    {"role": "system", "content": DECOMPOSITION_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "api_key": _API_KEY,
                "max_tokens": 2048,
            }
            # Only pass temperature for models that support it
            if "sonnet-5" not in _MODEL_COORDINATOR and "opus-4-7" not in _MODEL_COORDINATOR:
                kwargs["temperature"] = 0.2

            response = completion(**kwargs)
            raw = response.choices[0].message.content.strip()

            # Track coordinator tokens
            if response.usage:
                self.memory.track_tokens(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                    (response.usage.prompt_tokens * 3.0 / 1_000_000) + (response.usage.completion_tokens * 15.0 / 1_000_000)
                )

            # Parse JSON
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(raw)

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"[{self.task_id}] Decomposition failed: {e}")
            return {"agents": []}

    def _instantiate_agents(self, specs: list[dict]):
        """Create SwarmAgent instances from decomposition specs."""
        for spec in specs:
            role = spec["role"]
            skill_prompt = self._build_skill_prompt(role, spec.get("skill_context", ""))

            agent = SwarmAgent(
                agent_id=f"{self.task_id}-{role}",
                role=role,
                task=spec["task"],
                skill_prompt=skill_prompt,
                model_tier=spec.get("model_tier", "default"),
                memory=self.memory,
            )
            self.agents.append(agent)

    def _build_skill_prompt(self, role: str, skill_context: str) -> str:
        """Dynamically compose a skill prompt for this agent."""
        base = f"""You are a specialist agent: {role}.
Your expertise: {skill_context}

Rules:
- Produce exactly what is asked — no extra scope
- Be complete — no TODOs or placeholders
- Be precise — include file paths, function names, specific values
- If you produce code, include the file path as a comment on line 1
- Keep output concise and actionable"""

        # Load governance context if relevant
        try:
            from agents.steering_loader import load_shared_steering
            steering = load_shared_steering()
            if steering:
                base += f"\n\n--- Governance & Environment ---\n{steering[:1500]}"
        except Exception:
            pass

        return base

    def _build_execution_waves(self, specs: list[dict]) -> list[list[SwarmAgent]]:
        """
        Group agents into execution waves based on dependencies.
        Wave 0: agents with no dependencies (run first, in parallel)
        Wave 1: agents that depend on wave 0 agents
        ...
        """
        # Build dependency map
        role_to_agent = {a.role: a for a in self.agents}
        role_deps = {s["role"]: set(s.get("depends_on", [])) for s in specs}

        waves = []
        completed_roles: set = set()
        remaining = set(role_deps.keys())

        while remaining:
            # Find all agents whose dependencies are satisfied
            ready = [r for r in remaining if role_deps[r].issubset(completed_roles)]

            if not ready:
                # Circular dependency — force remaining into one wave
                logger.warning(f"[{self.task_id}] Circular deps detected, forcing: {remaining}")
                ready = list(remaining)

            wave = [role_to_agent[r] for r in ready if r in role_to_agent]
            waves.append(wave)

            for r in ready:
                completed_roles.add(r)
                remaining.discard(r)

        return waves

    def _execute_wave(self, wave: list[SwarmAgent]):
        """Execute a wave of agents in parallel."""
        if len(wave) == 1:
            wave[0].run()
            return

        with ThreadPoolExecutor(max_workers=min(len(wave), _MAX_WORKERS)) as pool:
            futures = {pool.submit(agent.run): agent for agent in wave}
            for future in as_completed(futures):
                agent = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"[{agent.agent_id}] Wave execution error: {e}")
                    agent.status = "failed"
                    agent.result = f"ERROR: {e}"

    def _synthesize(self, original_task: str) -> str:
        """Combine all agent results into a coherent final output."""
        agent_outputs = []
        for agent in self.agents:
            status_icon = "✅" if agent.status == "complete" else "❌"
            agent_outputs.append(f"{status_icon} **{agent.role}** ({agent.model_tier}): {agent.summary or 'No output'}")

        # For the final synthesis, include the last (usually most complete) agent's full result
        final_agent = next((a for a in reversed(self.agents) if a.status == "complete"), None)
        full_result = final_agent.result if final_agent else "No agents completed successfully."

        return f"""Swarm Execution Summary ({len(self.agents)} agents):

{chr(10).join(agent_outputs)}

---

{full_result}"""

    def _log_trace(self, task: str, token_usage: dict, latency_ms: int):
        """Log swarm execution to darius_traces."""
        try:
            from AI.darius.memory import log_trace
            log_trace(
                task_id=self.task_id,
                phase="complete",
                session_id=self.task_id,
                tool_name="agent_swarm",
                tool_args={
                    "task": task[:300],
                    "agent_count": len(self.agents),
                    "agents": [a.to_dict() for a in self.agents],
                },
                tool_result=json.dumps(token_usage),
                model="swarm-coordinator",
                tokens_in=token_usage.get("input", 0),
                tokens_out=token_usage.get("output", 0),
                latency_ms=latency_ms,
                status="success" if all(a.status == "complete" for a in self.agents) else "partial",
            )
        except Exception:
            pass
