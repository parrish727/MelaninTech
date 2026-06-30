"""
Template Engine — loads YAML workflow templates and executes them step-by-step.
Human approval gates are preserved: steps with approve: true pause for Slack approval.
Steps with type: approve are explicit human gates that block until approved.
"""
import os
import re
import yaml
from dataclasses import dataclass, field

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")


@dataclass
class TemplateStep:
    id: str
    type: str  # agent, approve, darius, shell
    agent: str | None = None
    task: str | None = None
    project: str | None = None
    message: str | None = None
    approve: bool = True
    depends_on: str | None = None


@dataclass
class Template:
    name: str
    trigger: str
    description: str
    params: dict = field(default_factory=dict)
    steps: list[TemplateStep] = field(default_factory=list)


def _resolve_vars(text: str, params: dict) -> str:
    """Replace {{var}} placeholders with param values."""
    if not text:
        return text
    for key, val in params.items():
        text = text.replace(f"{{{{{key}}}}}", str(val))
    return text


def load_template(trigger: str) -> Template | None:
    """Load a template by its trigger name."""
    for fname in os.listdir(_TEMPLATES_DIR):
        if not fname.endswith((".yaml", ".yml")):
            continue
        path = os.path.join(_TEMPLATES_DIR, fname)
        with open(path) as f:
            data = yaml.safe_load(f)
        if data and data.get("trigger") == trigger:
            steps = []
            for s in data.get("steps", []):
                steps.append(TemplateStep(
                    id=s["id"],
                    type=s.get("type", "agent"),
                    agent=s.get("agent"),
                    task=s.get("task"),
                    project=s.get("project"),
                    message=s.get("message"),
                    approve=s.get("approve", True),
                    depends_on=s.get("depends_on"),
                ))
            return Template(
                name=data["name"],
                trigger=data["trigger"],
                description=data.get("description", ""),
                params=data.get("params", {}),
                steps=steps,
            )
    return None


def list_templates() -> list[dict]:
    """List all available templates."""
    templates = []
    for fname in sorted(os.listdir(_TEMPLATES_DIR)):
        if not fname.endswith((".yaml", ".yml")):
            continue
        path = os.path.join(_TEMPLATES_DIR, fname)
        with open(path) as f:
            data = yaml.safe_load(f)
        if data and data.get("trigger"):
            templates.append({"trigger": data["trigger"], "name": data["name"], "description": data.get("description", "")})
    return templates


def resolve_template(template: Template, user_params: dict) -> list[dict]:
    """
    Resolve a template with user-provided params into executable steps.
    Returns a list of step dicts ready for execution.
    Each step has: id, type, agent, task, project, message, approve, depends_on
    """
    # Merge defaults with user params
    resolved_params = {}
    for key, spec in template.params.items():
        if isinstance(spec, dict):
            if key in user_params:
                resolved_params[key] = user_params[key]
            elif spec.get("required") and key not in user_params:
                raise ValueError(f"Required parameter '{key}' not provided for template '{template.trigger}'")
            else:
                resolved_params[key] = spec.get("default", "")
        else:
            resolved_params[key] = user_params.get(key, spec)

    # Resolve variables in each step
    executable_steps = []
    for step in template.steps:
        executable_steps.append({
            "id": step.id,
            "type": step.type,
            "agent": _resolve_vars(step.agent, resolved_params) if step.agent else None,
            "task": _resolve_vars(step.task, resolved_params) if step.task else None,
            "project": _resolve_vars(step.project, resolved_params) if step.project else None,
            "message": _resolve_vars(step.message, resolved_params) if step.message else None,
            "approve": step.approve,
            "depends_on": step.depends_on,
        })
    return executable_steps


def parse_template_command(text: str) -> tuple[str | None, dict]:
    """
    Parse a Slack message to detect template trigger and params.
    Examples:
        "deploy-website" → ("deploy-website", {})
        "onboard-client --slug acme --domain acme.com" → ("onboard-client", {"slug": "acme", "domain": "acme.com"})
        "build-feature --project melanin-tech-website --feature add contact form --agent frontend"
    """
    parts = text.strip().split()
    if not parts:
        return None, {}

    trigger = parts[0].lower()
    template = load_template(trigger)
    if not template:
        return None, {}

    # Parse --key value params
    params = {}
    i = 1
    while i < len(parts):
        if parts[i].startswith("--"):
            key = parts[i][2:]
            # Collect value (may be multi-word until next --)
            val_parts = []
            i += 1
            while i < len(parts) and not parts[i].startswith("--"):
                val_parts.append(parts[i])
                i += 1
            params[key] = " ".join(val_parts)
        else:
            i += 1

    return trigger, params
