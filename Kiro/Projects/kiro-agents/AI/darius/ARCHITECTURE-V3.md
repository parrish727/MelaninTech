# Darius v3 Architecture: Delta Context + Agent Swarm

## Overview

This document proposes two architectural changes to Darius that eliminate the primary inefficiencies in the current system: redundant token processing and rigid agent topology.

**Current state (Darius v2.0):**
- smolagents ToolCallingAgent sends full conversation history every step (O(n²) token growth)
- DAG executor uses pre-defined agent roster with fixed capabilities
- Sub-agents are isolated — no shared memory between parallel steps
- Planning is a single LLM call that produces a static graph

**Proposed state (Darius v3):**
- Custom execution harness with delta context management (O(n) token growth)
- Dynamic agent instantiation from skill templates
- Shared memory layer (Redis) for cross-agent coordination
- Adaptive planning that can revise the DAG mid-execution

---

## 1. Delta Context Management

### Problem

smolagents sends the FULL message history on every LLM call in a multi-step loop:

```
Step 1:  system + task + context                    = 15K tokens
Step 2:  system + task + context + step1            = 20K tokens  
Step 3:  system + task + context + step1 + step2    = 25K tokens
...
Step 10: system + task + context + steps 1-9        = 55K tokens
```

Total tokens for a 10-step task: ~350K input tokens. At $3/MTok (Sonnet), that's $1.05 per complex task.

### Solution: Delta Harness

Replace smolagents with a custom execution loop that maintains state externally and only sends the LLM what changed:

```
Step 1:  system + task + context                    = 15K tokens (cold start)
Step 2:  system + summary(step1) + next_action      = 5K tokens
Step 3:  system + summary(step2) + next_action      = 5K tokens
...
Step 10: system + summary(step9) + next_action      = 5K tokens
```

Total tokens: ~60K input tokens. **83% reduction.**

### Implementation

```python
class DeltaExecutor:
    """
    Custom execution harness that replaces smolagents.
    Maintains state in Redis, feeds only deltas to the LLM.
    """
    
    def __init__(self, task_id: str, model: str):
        self.task_id = task_id
        self.model = model
        self.state = RedisState(task_id)  # persistent across steps
        
    def run(self, task: str, context: str, max_steps: int = 15):
        # Step 1: Initial planning (full context)
        plan = self._plan(task, context)
        self.state.set("plan", plan)
        self.state.set("completed_steps", [])
        
        for step in plan:
            # Only send: system prompt + current step + delta from last step
            delta = self.state.get_delta()  # what changed since last step
            result = self._execute_step(step, delta)
            
            # Compress result to summary before storing
            summary = self._compress(result)  # ~200 tokens max
            self.state.append("completed_steps", {
                "step": step["id"],
                "summary": summary,
                "full_result": result,  # stored but not sent to LLM
            })
            
            # Evaluate: does the plan need revision?
            if self._needs_replanning(result, plan):
                plan = self._replan(task, self.state.get_delta())
                self.state.set("plan", plan)
        
        return self.state.get("completed_steps")
    
    def _execute_step(self, step: dict, delta: str) -> str:
        """Single LLM call with minimal context."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},  # cached by Anthropic
            {"role": "user", "content": f"Previous: {delta}\n\nNow do: {step['task']}"},
        ]
        return litellm.completion(model=self.model, messages=messages)
    
    def _compress(self, result: str) -> str:
        """Reduce a step result to a ~200 token summary."""
        # Use Haiku for compression (cheap, fast)
        return litellm.completion(
            model="anthropic/claude-haiku-4-5-20251001",
            messages=[{"role": "user", "content": f"Summarize in 2 sentences: {result[:2000]}"}],
            max_tokens=100,
        )
```

### Key Design Decisions

1. **System prompt is constant** → Anthropic's server-side cache handles this (free after first call in 5-min window)
2. **Previous steps are compressed** → each step gets a ~200 token summary, not the full output
3. **Full results stored in Redis** → available if needed (e.g., file contents for a write operation) but not re-sent to LLM
4. **Replanning is possible** → if a step fails or reveals new information, the executor can revise the remaining plan

### Token Savings Estimate

| Task Type | Current (smolagents) | Proposed (delta) | Savings |
|-----------|---------------------|------------------|---------|
| 3-step simple | ~45K tokens | ~25K tokens | 44% |
| 5-step implementation | ~120K tokens | ~40K tokens | 67% |
| 10-step refactor | ~350K tokens | ~60K tokens | 83% |
| 15-step architecture | ~600K tokens | ~80K tokens | 87% |

---

## 2. Agent Swarm Pattern

### Problem (Current DAG Executor)

- Agents are **pre-defined containers** (frontend-agent, backend-agent, etc.)
- Each has a **fixed skill file** and **fixed system prompt**
- Planning produces a **static DAG** that can't adapt mid-execution
- Sub-agents are **isolated** — step 2 can't see step 3's partial output
- No **dynamic specialization** — you can't spin up a "HIPAA compliance reviewer" on the fly

### Solution: Dynamic Agent Swarm

Instead of routing to pre-built containers, the swarm instantiates **ephemeral agents** from skill templates with shared memory:

```
┌─────────────────────────────────────────────────┐
│  Darius (Coordinator)                           │
│  - Decomposes task into sub-tasks               │
│  - Instantiates specialist agents dynamically   │
│  - Monitors shared memory for completion        │
│  - Handles coordination and conflict resolution │
└────────────┬──────────────┬─────────────────────┘
             │              │
    ┌────────▼───┐  ┌───────▼────────┐
    │  Agent A   │  │   Agent B      │
    │  (spawned) │  │   (spawned)    │
    │            │  │                │
    │  Reads:    │  │  Reads:        │
    │  - task    │  │  - task        │
    │  - shared  │  │  - shared      │
    │    memory  │  │    memory      │
    │            │  │                │
    │  Writes:   │  │  Writes:       │
    │  - result  │  │  - result      │
    │  - signals │  │  - signals     │
    └────────────┘  └────────────────┘
             │              │
    ┌────────▼──────────────▼─────────┐
    │  Redis Shared Memory             │
    │  - Task state per agent          │
    │  - Cross-agent signals           │
    │  - Partial results               │
    │  - Conflict detection            │
    └──────────────────────────────────┘
```

### Implementation

```python
class AgentSwarm:
    """
    Dynamic agent swarm — instantiates specialist agents on the fly
    from skill templates, with shared Redis memory for coordination.
    """
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.memory = SharedMemory(task_id)  # Redis-backed
        self.agents: list[SwarmAgent] = []
    
    def execute(self, task: str, context: str) -> str:
        # 1. Decompose into sub-tasks with specializations
        decomposition = self._decompose(task, context)
        
        # 2. Instantiate agents dynamically
        for sub_task in decomposition["agents"]:
            agent = SwarmAgent(
                agent_id=f"{self.task_id}-{sub_task['role']}",
                role=sub_task["role"],           # e.g., "HIPAA reviewer"
                skill=sub_task["skill_prompt"],  # generated on the fly
                model=sub_task["model"],         # tiered: opus/sonnet/haiku
                memory=self.memory,             # shared across all agents
            )
            self.agents.append(agent)
        
        # 3. Execute in parallel where possible
        # Agents can read each other's partial results via shared memory
        results = self._execute_parallel(decomposition["execution_order"])
        
        # 4. Coordinator synthesizes final output
        return self._synthesize(results)
    
    def _decompose(self, task: str, context: str) -> dict:
        """
        Use Sonnet 5 to decompose task into:
        - Sub-tasks with specific goals
        - Required agent roles (dynamically defined)
        - Execution order (which can run in parallel)
        - Model tier per agent (cheap agents for simple sub-tasks)
        """
        return litellm.completion(
            model="anthropic/claude-sonnet-5",
            messages=[{
                "role": "user",
                "content": DECOMPOSITION_PROMPT.format(task=task, context=context)
            }],
        )
    
    def _execute_parallel(self, execution_order: list[list[str]]):
        """Execute agents in waves — each wave runs in parallel."""
        from concurrent.futures import ThreadPoolExecutor
        
        for wave in execution_order:
            with ThreadPoolExecutor(max_workers=len(wave)) as pool:
                futures = {
                    pool.submit(agent.run): agent
                    for agent in self.agents
                    if agent.agent_id in wave
                }
                for future in futures:
                    future.result()  # results written to shared memory


class SwarmAgent:
    """A single ephemeral agent in the swarm."""
    
    def __init__(self, agent_id, role, skill, model, memory):
        self.agent_id = agent_id
        self.role = role
        self.skill = skill
        self.model = model
        self.memory = memory
    
    def run(self):
        """Execute using delta context — read shared memory, do work, write results."""
        # Read relevant context from shared memory
        context = self.memory.get_relevant(self.agent_id)
        
        # Execute with DeltaExecutor (not smolagents)
        executor = DeltaExecutor(self.agent_id, self.model)
        result = executor.run(self.skill, context)
        
        # Write results back to shared memory
        self.memory.write(self.agent_id, result)
        
        # Signal completion
        self.memory.signal(self.agent_id, "complete")
```

### Key Differences from Current DAG Executor

| Aspect | Current (v2) | Proposed (v3) |
|--------|-------------|---------------|
| Agent definition | Pre-built Docker containers | Ephemeral, instantiated per-task |
| Skill assignment | Fixed skill.md files | Generated from templates + task context |
| Communication | Isolated (output → input only) | Shared Redis memory (read anytime) |
| Model selection | Per-task (same model for all steps) | Per-agent (cheap agents for cheap sub-tasks) |
| Plan modification | Static (plan once, execute) | Adaptive (replan if step fails or reveals info) |
| Parallelism | Level-based (topological sort) | True parallel with coordination signals |

### Shared Memory Schema (Redis)

```
swarm:{task_id}:plan           → JSON (current execution plan)
swarm:{task_id}:agents         → SET (active agent IDs)
swarm:{task_id}:agent:{id}:status → "running" | "complete" | "failed"
swarm:{task_id}:agent:{id}:result → compressed result text
swarm:{task_id}:agent:{id}:files  → LIST of file paths modified
swarm:{task_id}:signals        → LIST (coordination events)
swarm:{task_id}:conflicts      → LIST (detected conflicts, e.g., two agents editing same file)
```

---

## 3. Integration Plan

### Phase 1: Delta Executor (Week 1-2)
- Build `DeltaExecutor` class alongside existing smolagents code
- Wire `/task` endpoint to use DeltaExecutor when `model_source != "legacy"`
- Keep smolagents as fallback (feature flag)
- Measure token savings on real tasks

### Phase 2: Shared Memory (Week 2-3)
- Implement `SharedMemory` Redis layer
- Update existing DAG executor to use shared memory (incremental)
- Add conflict detection (two agents modifying same file)
- Add cross-agent signal handling

### Phase 3: Dynamic Swarm (Week 3-4)
- Build `AgentSwarm` class
- Implement dynamic skill generation (template + task context → agent prompt)
- Per-agent model selection (Haiku for simple sub-tasks, Sonnet for implementation, Opus for architecture)
- Replace pre-built container dispatch with swarm dispatch for complex tasks

### Phase 4: Self-Improvement Loop (Week 4+)
- Swarm traces → training data extraction
- Failed evaluations → automatic skill refinement proposals
- Token usage tracking per swarm execution → cost optimization feedback

---

## 4. Hardware Requirements

No additional hardware needed. The swarm runs on the same infrastructure:
- **LLM calls:** Still go through Anthropic API (Claude) — the swarm is an orchestration pattern, not a model change
- **Redis:** Already deployed, already used by agents — just more keys
- **Compute:** ThreadPoolExecutor for parallelism (same as current DAG executor)
- **Storage:** Compressed results in Redis (TTL-based, auto-cleanup)

The token savings (67-87%) mean we actually REDUCE our Anthropic API costs while getting better results.

---

## 5. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Delta compression loses critical info | Medium | High | Store full results in Redis; agent can request expansion |
| Swarm agents conflict (edit same file) | Medium | Medium | Conflict detection in shared memory; coordinator resolves |
| Increased Redis memory usage | Low | Low | TTL on all swarm keys (1hr); cleanup after task completion |
| Complexity increase in debugging | Medium | Medium | Full trace logging to darius_traces; replay capability |
| Regression vs smolagents quality | Low | High | Run both in parallel during Phase 1; compare outputs |

---

## 6. Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Tokens per 5-step task | ~120K | <40K |
| Cost per complex task | ~$1.05 | <$0.35 |
| Multi-step task latency | 60-120s | 30-60s |
| Agent evaluation pass rate | ~70% | >85% |
| Tasks requiring human intervention | ~15% | <5% |

---

## Decision Required

Approve to proceed with Phase 1 (Delta Executor) as a non-breaking addition alongside existing smolagents code? This de-risks the approach — we can A/B test before committing to the full swarm architecture.
