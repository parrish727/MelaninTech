"""
Skill Refinement Engine — Proposes prompt/skill updates based on failure patterns.

When the analyzer identifies recurring failures or skill gaps, this engine:
1. Examines the failed traces for root cause
2. Reads the relevant skill file or prompt template
3. Uses Claude to propose specific improvements
4. Stores proposals for human review (never auto-applies)

The improvement cycle:
  analyze → identify gaps → propose refinements → review → apply
"""
import os
import json
import time
import logging
from pathlib import Path
from litellm import completion

logger = logging.getLogger("darius.swarm.refiner")

_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
_MODEL = "anthropic/claude-sonnet-4-6"  # Use proven model for refinement proposals
_SKILLS_DIR = Path(os.environ.get("SKILLS_DIR", "/app/agents/skills"))
_TEMPLATES_DIR = Path(os.environ.get("TEMPLATES_DIR", "/app/AI/darius/swarm/templates"))

REFINEMENT_PROMPT = """You are a prompt engineering specialist. You analyze failure patterns in an AI agent system and propose specific improvements to the agent's skill files or prompt templates.

Given:
- The current skill/prompt content
- Failure patterns (what went wrong, how often)
- Sample error messages

Propose SPECIFIC, MINIMAL changes to the skill/prompt that would prevent these failures. 
- Do NOT rewrite the entire file
- Propose targeted additions or modifications
- Explain WHY each change would help
- Format as a diff-style proposal

Output format:
{
  "file": "<path to the file being modified>",
  "changes": [
    {
      "type": "add",
      "location": "after line containing X",
      "content": "new content to add",
      "reason": "why this fixes the failure pattern"
    }
  ],
  "confidence": 0.0-1.0,
  "expected_impact": "what should improve after this change"
}"""


class SkillRefiner:
    """
    Proposes skill/prompt refinements based on failure analysis.
    All proposals are stored for human review — never auto-applied.
    """

    def __init__(self):
        self.proposals: list[dict] = []

    def refine(self, insights: dict) -> list[dict]:
        """
        Generate refinement proposals from analyzer insights.

        Args:
            insights: output from analyzer.analyze()

        Returns:
            list of proposal dicts, each containing the proposed change
        """
        self.proposals = []

        # Process failure patterns
        for pattern in insights.get("failure_patterns", []):
            proposal = self._propose_for_failure(pattern)
            if proposal:
                self.proposals.append(proposal)

        # Process skill gaps
        for gap in insights.get("skill_gaps", []):
            proposal = self._propose_for_gap(gap)
            if proposal:
                self.proposals.append(proposal)

        # Process model performance issues
        for mp in insights.get("model_performance", []):
            if mp.get("success_rate", 100) < 80 and mp.get("calls", 0) > 3:
                proposal = self._propose_model_adjustment(mp)
                if proposal:
                    self.proposals.append(proposal)

        return self.proposals

    def _propose_for_failure(self, pattern: dict) -> dict | None:
        """Generate a refinement proposal for a recurring failure pattern."""
        tool = pattern.get("tool", "unknown")
        phase = pattern.get("phase", "unknown")
        errors = pattern.get("sample_errors", [])

        if not errors:
            return None

        # Identify which skill file is relevant
        skill_file = self._find_relevant_skill(tool, phase)
        if not skill_file:
            return {
                "type": "new_skill_needed",
                "tool": tool,
                "phase": phase,
                "failure_count": pattern.get("count", 0),
                "reason": f"No skill file found for tool '{tool}' in phase '{phase}'. Consider creating one.",
                "sample_errors": errors[:2],
            }

        # Read current skill content
        skill_content = self._read_file(skill_file)
        if not skill_content:
            return None

        # Ask Claude to propose a fix
        try:
            prompt = f"""Failure pattern:
- Tool: {tool}
- Phase: {phase}  
- Occurrences: {pattern.get('count', 0)}
- Sample errors: {json.dumps(errors[:3])}

Current skill file ({skill_file}):
```
{skill_content[:3000]}
```

Propose a minimal change to prevent this failure pattern."""

            response = completion(
                model=_MODEL,
                messages=[
                    {"role": "system", "content": REFINEMENT_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                api_key=_API_KEY,
                max_tokens=1024,
                temperature=0.3,
            )

            raw = response.choices[0].message.content.strip()
            # Try to parse as JSON
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            proposal = json.loads(raw)
            proposal["source"] = "failure_pattern"
            proposal["pattern"] = pattern
            return proposal

        except Exception as e:
            logger.warning(f"Refinement proposal failed: {e}")
            return None

    def _propose_for_gap(self, gap: dict) -> dict | None:
        """Generate a proposal for a skill gap (task type that repeatedly fails)."""
        task_pattern = gap.get("task_pattern", "")
        failure_rate = gap.get("failure_rate", 0)

        if failure_rate < 50:
            return None

        return {
            "type": "skill_gap",
            "task_pattern": task_pattern[:200],
            "failure_rate": failure_rate,
            "attempts": gap.get("attempts", 0),
            "reason": f"Tasks matching this pattern fail {failure_rate}% of the time. The current skill set may not cover this domain adequately.",
            "recommendation": "Review task pattern and add domain-specific instructions to the relevant skill file or create a new specialist template.",
        }

    def _propose_model_adjustment(self, mp: dict) -> dict | None:
        """Propose switching a model tier based on performance data."""
        model = mp.get("model", "")
        success_rate = mp.get("success_rate", 100)

        return {
            "type": "model_adjustment",
            "model": model,
            "success_rate": success_rate,
            "calls": mp.get("calls", 0),
            "reason": f"Model '{model}' has {success_rate}% success rate over {mp.get('calls', 0)} calls. Consider routing these tasks to a more capable tier.",
            "recommendation": f"Move tasks currently using '{model}' up one tier (e.g., haiku→sonnet, sonnet→opus) or add more specific instructions to reduce failures.",
        }

    def _find_relevant_skill(self, tool: str, phase: str) -> str | None:
        """Map a tool/phase to the most relevant skill file."""
        # Map tool names to skill files
        tool_skill_map = {
            "agent:frontend": "frontend.skill.md",
            "agent:backend": "backend.skill.md",
            "agent:deploy": "deploy.skill.md",
            "agent:scaffold": "scaffold.skill.md",
            "agent:support": "support.skill.md",
            "agent:code": "code.skill.md",
            "agent:file": "file.skill.md",
            "agent:darius": "darius.skill.md",
            "agent:sre": "sre.skill.md",
            "agent:qa": "qa.skill.md",
            "delta_executor": "templates/specialist.md",
            "agent_swarm": "templates/coordinator.md",
            "planner": "templates/coordinator.md",
            "chat": "darius-hud.skill.md",
        }

        skill_name = tool_skill_map.get(tool)
        if skill_name:
            if skill_name.startswith("templates/"):
                path = _TEMPLATES_DIR / skill_name.replace("templates/", "")
            else:
                path = _SKILLS_DIR / skill_name
            if path.exists():
                return str(path)

        # Phase-based fallback — for internal Darius phases that have no tool
        phase_skill_map = {
            "evaluate": "darius-evaluate.skill.md",
            "revise": "darius-revise.skill.md",
            "reject": "darius-reject.skill.md",
        }

        phase_skill = phase_skill_map.get(phase)
        if phase_skill:
            path = _SKILLS_DIR / phase_skill
            if path.exists():
                return str(path)

        return None

    def _read_file(self, path: str) -> str:
        """Read a file's content."""
        try:
            return Path(path).read_text(encoding="utf-8")
        except Exception:
            return ""

    def format_proposals(self) -> str:
        """Format proposals for human-readable output (Slack/HUD)."""
        if not self.proposals:
            return "No refinement proposals generated. System performing within expected parameters."

        lines = [f"## Skill Refinement Proposals ({len(self.proposals)} total)\n"]

        for i, p in enumerate(self.proposals, 1):
            ptype = p.get("type", "unknown")
            lines.append(f"### Proposal {i}: {ptype}")

            if ptype == "new_skill_needed":
                lines.append(f"- Tool: `{p.get('tool')}`")
                lines.append(f"- Failures: {p.get('failure_count')}")
                lines.append(f"- Reason: {p.get('reason')}")
            elif ptype == "skill_gap":
                lines.append(f"- Pattern: `{p.get('task_pattern', '')[:80]}`")
                lines.append(f"- Failure rate: {p.get('failure_rate')}%")
                lines.append(f"- Recommendation: {p.get('recommendation')}")
            elif ptype == "model_adjustment":
                lines.append(f"- Model: `{p.get('model')}`")
                lines.append(f"- Success rate: {p.get('success_rate')}%")
                lines.append(f"- Recommendation: {p.get('recommendation')}")
            else:
                lines.append(f"- File: `{p.get('file', 'N/A')}`")
                lines.append(f"- Confidence: {p.get('confidence', 'N/A')}")
                lines.append(f"- Expected impact: {p.get('expected_impact', 'N/A')}")
                for change in p.get("changes", []):
                    lines.append(f"  - {change.get('type')}: {change.get('reason', '')[:100]}")

            lines.append("")

        return "\n".join(lines)
