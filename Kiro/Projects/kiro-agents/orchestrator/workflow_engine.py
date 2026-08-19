"""
File-Tree Workflow Engine — workflows as directories, not just YAML.

Structure:
  workflows/
  ├── .meta/
  │   └── engine.json          ← Engine config (this file describes format)
  ├── build-feature/
  │   ├── workflow.yaml         ← Steps + dependencies + metadata
  │   ├── context/              ← Scoped RAG data for this workflow
  │   │   └── past_runs.jsonl
  │   └── steps/
  │       ├── 01-implement/
  │       │   ├── instructions.md   ← Prompt/skill for this step
  │       │   ├── tools.json        ← Which tools this step can use
  │       │   └── output/           ← Results stored here per run
  │       └── 02-qa/
  │           ├── instructions.md
  │           └── tools.json
  └── [workflow-name]/
      └── ...

Key principles:
  1. Darius can CREATE new workflow directories at runtime
  2. Darius can MODIFY instructions.md based on past run feedback
  3. Each step declares its own tools (subset of _registry.json)
  4. Output is stored per-run for training data extraction
  5. Existing YAML templates are backward-compatible (loaded via adapter)
"""
import os
import json
import yaml
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("workflow_engine")

_WORKFLOWS_DIR = Path(os.environ.get("WORKFLOWS_DIR", "/app/workflows"))
_TEMPLATES_DIR = Path(os.environ.get("TEMPLATES_DIR", "/app/templates"))


# ── Workflow Loading ──────────────────────────────────────────────────────────

def list_workflows() -> list[dict]:
    """List all available workflows (file-tree + legacy YAML templates)."""
    workflows = []

    # File-tree workflows
    if _WORKFLOWS_DIR.exists():
        for d in sorted(_WORKFLOWS_DIR.iterdir()):
            if d.is_dir() and not d.name.startswith("."):
                meta = _load_workflow_meta(d)
                if meta:
                    workflows.append(meta)

    # Legacy YAML templates (backward compat)
    if _TEMPLATES_DIR.exists():
        for f in sorted(_TEMPLATES_DIR.glob("*.yaml")):
            if f.name == "README.md":
                continue
            try:
                with open(f) as fh:
                    data = yaml.safe_load(fh)
                if data and data.get("trigger"):
                    workflows.append({
                        "name": data.get("name", f.stem),
                        "trigger": data["trigger"],
                        "description": data.get("description", ""),
                        "type": "legacy_yaml",
                        "path": str(f),
                        "steps": len(data.get("steps", [])),
                    })
            except Exception:
                continue

    return workflows


def _load_workflow_meta(path: Path) -> dict | None:
    """Load workflow metadata from a directory."""
    workflow_file = path / "workflow.yaml"
    if not workflow_file.exists():
        return None
    try:
        with open(workflow_file) as f:
            data = yaml.safe_load(f)
        steps_dir = path / "steps"
        step_count = len(list(steps_dir.iterdir())) if steps_dir.exists() else 0
        return {
            "name": data.get("name", path.name),
            "trigger": data.get("trigger", path.name),
            "description": data.get("description", ""),
            "type": "file_tree",
            "path": str(path),
            "steps": step_count,
            "params": data.get("params", {}),
        }
    except Exception as e:
        logger.warning(f"Failed to load workflow {path}: {e}")
        return None


def load_workflow(name: str) -> dict | None:
    """Load a complete workflow by name/trigger — checks file-tree first, then legacy."""
    # Check file-tree workflows
    workflow_path = _WORKFLOWS_DIR / name
    if workflow_path.exists() and (workflow_path / "workflow.yaml").exists():
        return _load_file_tree_workflow(workflow_path)

    # Check legacy templates
    for f in _TEMPLATES_DIR.glob("*.yaml"):
        try:
            with open(f) as fh:
                data = yaml.safe_load(fh)
            if data and data.get("trigger") == name:
                return {"type": "legacy_yaml", "data": data, "path": str(f)}
        except Exception:
            continue

    return None


def _load_file_tree_workflow(path: Path) -> dict:
    """Load a file-tree workflow with all steps and their instructions."""
    with open(path / "workflow.yaml") as f:
        meta = yaml.safe_load(f)

    steps = []
    steps_dir = path / "steps"
    if steps_dir.exists():
        for step_dir in sorted(steps_dir.iterdir()):
            if not step_dir.is_dir():
                continue
            step = {"id": step_dir.name, "path": str(step_dir)}

            # Load instructions
            instructions_file = step_dir / "instructions.md"
            if instructions_file.exists():
                step["instructions"] = instructions_file.read_text()

            # Load tools config
            tools_file = step_dir / "tools.json"
            if tools_file.exists():
                step["tools"] = json.loads(tools_file.read_text())

            steps.append(step)

    return {
        "type": "file_tree",
        "name": meta.get("name", path.name),
        "trigger": meta.get("trigger", path.name),
        "description": meta.get("description", ""),
        "params": meta.get("params", {}),
        "steps": steps,
        "path": str(path),
    }


# ── Workflow Creation (Darius can call this) ──────────────────────────────────

def create_workflow(
    name: str,
    description: str,
    steps: list[dict],
    params: dict = None,
) -> dict:
    """
    Create a new file-tree workflow. Darius calls this to generate workflows at runtime.

    Args:
        name: Workflow name (becomes directory name)
        description: What the workflow does
        steps: List of step dicts: [{"id": "01-step", "instructions": "...", "tools": [...], "agent": "..."}]
        params: Optional workflow parameters

    Returns:
        Workflow metadata dict
    """
    workflow_dir = _WORKFLOWS_DIR / name
    workflow_dir.mkdir(parents=True, exist_ok=True)

    # Write workflow.yaml
    meta = {
        "name": name.replace("-", " ").title(),
        "trigger": name,
        "description": description,
        "params": params or {},
        "created_at": datetime.now().isoformat(),
        "created_by": "darius",
    }
    with open(workflow_dir / "workflow.yaml", "w") as f:
        yaml.dump(meta, f, default_flow_style=False)

    # Create context directory
    (workflow_dir / "context").mkdir(exist_ok=True)

    # Create steps
    steps_dir = workflow_dir / "steps"
    steps_dir.mkdir(exist_ok=True)

    for i, step in enumerate(steps):
        step_id = step.get("id", f"{i+1:02d}-step-{i+1}")
        step_dir = steps_dir / step_id
        step_dir.mkdir(exist_ok=True)

        # Write instructions.md
        instructions = step.get("instructions", f"# Step: {step_id}\n\nExecute this step.")
        (step_dir / "instructions.md").write_text(instructions)

        # Write tools.json
        tools = step.get("tools", ["read_file", "write_file", "shell"])
        tool_config = {
            "allowed_tools": tools,
            "agent": step.get("agent", "darius"),
            "approve": step.get("approve", True),
            "depends_on": step.get("depends_on", []),
        }
        with open(step_dir / "tools.json", "w") as f:
            json.dump(tool_config, f, indent=2)

        # Create output directory
        (step_dir / "output").mkdir(exist_ok=True)

    logger.info(f"Created workflow: {name} ({len(steps)} steps)")
    return _load_workflow_meta(workflow_dir)


def store_run_output(workflow_name: str, step_id: str, run_id: str, output: str, status: str = "success"):
    """Store the output of a workflow step run for training data."""
    step_dir = _WORKFLOWS_DIR / workflow_name / "steps" / step_id / "output"
    step_dir.mkdir(parents=True, exist_ok=True)

    run_file = step_dir / f"{run_id}.json"
    run_data = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "output": output[:50000],  # Cap at 50KB
    }
    with open(run_file, "w") as f:
        json.dump(run_data, f, indent=2)


def store_run_context(workflow_name: str, run_id: str, task: str, result_summary: str, approved: bool):
    """Append a run record to the workflow's context for scoped RAG."""
    context_dir = _WORKFLOWS_DIR / workflow_name / "context"
    context_dir.mkdir(parents=True, exist_ok=True)

    past_runs = context_dir / "past_runs.jsonl"
    record = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "task": task,
        "result_summary": result_summary[:2000],
        "approved": approved,
    }
    with open(past_runs, "a") as f:
        f.write(json.dumps(record) + "\n")


# ── Workflow Modification (Darius can update instructions) ────────────────────

def update_step_instructions(workflow_name: str, step_id: str, new_instructions: str):
    """Update the instructions for a workflow step (self-improvement)."""
    instructions_file = _WORKFLOWS_DIR / workflow_name / "steps" / step_id / "instructions.md"
    if not instructions_file.parent.exists():
        raise ValueError(f"Step {step_id} not found in workflow {workflow_name}")

    # Keep a backup
    if instructions_file.exists():
        backup = instructions_file.with_suffix(f".md.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        shutil.copy2(instructions_file, backup)

    instructions_file.write_text(new_instructions)
    logger.info(f"Updated instructions for {workflow_name}/{step_id}")


# ── Migration: Convert legacy YAML to file-tree ──────────────────────────────

def migrate_template(trigger: str) -> dict | None:
    """Convert a legacy YAML template to file-tree format."""
    # Find the template
    for f in _TEMPLATES_DIR.glob("*.yaml"):
        try:
            with open(f) as fh:
                data = yaml.safe_load(fh)
            if data and data.get("trigger") == trigger:
                break
        except Exception:
            continue
    else:
        return None

    # Convert to file-tree steps
    steps = []
    for step in data.get("steps", []):
        steps.append({
            "id": step["id"],
            "instructions": f"# {step.get('type', 'agent').title()} Step\n\n{step.get('task', step.get('message', ''))}",
            "tools": _default_tools_for_agent(step.get("agent", "darius")),
            "agent": step.get("agent", "darius"),
            "approve": step.get("approve", True),
            "depends_on": [step["depends_on"]] if step.get("depends_on") else [],
        })

    return create_workflow(
        name=trigger,
        description=data.get("description", ""),
        steps=steps,
        params=data.get("params", {}),
    )


def _default_tools_for_agent(agent: str) -> list[str]:
    """Return default tool set for an agent type."""
    tool_sets = {
        "frontend": ["read_file", "write_file", "mcp", "dispatch"],
        "backend": ["read_file", "write_file", "shell", "mcp", "dispatch"],
        "deploy": ["shell", "gateway", "mcp"],
        "qa": ["read_file", "shell", "mcp"],
        "darius": ["read_file", "write_file", "shell", "git", "mcp", "gateway", "dispatch", "web_search"],
        "scaffold": ["read_file", "write_file", "shell", "git"],
    }
    return tool_sets.get(agent, ["read_file", "write_file", "mcp"])
