"""
Steering Loader — Bridges .kiro/steering/ framework into the agent runtime.

Loads guardrails, parameters, skills, tools, and shared context from the
Enterprise AI Agent Framework and injects them into agent system prompts.

The steering directory can be:
1. Symlinked from the workspace .kiro/steering/ into the Docker container
2. Mounted as a volume in docker-compose.yml
3. Copied at build time

Resolution order:
1. STEERING_DIR env var (explicit override)
2. /app/.kiro/steering/ (Docker volume mount)
3. Relative to this file: ../../.kiro/steering/ (local dev)
4. Workspace root: /Users/pktech_dev/Documents/MelaninTechnologies/.kiro/steering/ (fallback)
"""
import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Agent name → steering subdirectory mapping
AGENT_STEERING_MAP: dict[str, str] = {
    "deploy": "devops",
    "devops": "devops",
    "support": "sre",
    "sre": "sre",
    "qa": "sre",
    "dba": "dba",
    "backend": "ai-engineer",
    "code": "ai-engineer",
    "frontend": "ai-engineer",
    "scaffold": "ai-engineer",
    "file": "ai-engineer",
    "uxui": "ai-engineer",
    "darius": "shared",  # Darius gets shared context only
}

# Files to load per agent type
AGENT_FILES: dict[str, list[str]] = {
    "devops": ["Guardrails.md", "Parameters.md", "Skills.md", "Tools.md"],
    "sre": ["Guardrails.md", "Parameters.md", "Skills.md", "Tools.md", "Environments.md", "Security.md"],
    "dba": ["Guardrails.md", "Parameters.md"],
    "ai-engineer": ["Guardrails.md", "Parameters.md", "Skills.md", "Tools.md", "Environments.md", "Security.md"],
    "shared": ["Environments.md", "Security.md"],
}

# Shared files that ALL agents receive
SHARED_FILES: list[str] = ["Environments.md", "Security.md", "AgentBehavior.md"]


def _resolve_steering_dir() -> Optional[Path]:
    """Find the steering directory from multiple possible locations."""
    candidates = [
        os.environ.get("STEERING_DIR", ""),
        "/app/.kiro/steering",
        str(Path(__file__).parent.parent.parent / ".kiro" / "steering"),
        "/Users/pktech_dev/Documents/MelaninTechnologies/.kiro/steering",
    ]

    for candidate in candidates:
        if candidate and Path(candidate).is_dir():
            return Path(candidate)

    return None


def _load_file(path: Path) -> str:
    """Load a markdown file, stripping YAML frontmatter if present."""
    try:
        content = path.read_text(encoding="utf-8")
        # Strip frontmatter (---)
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2].strip()
        return content
    except (OSError, IOError) as e:
        logger.debug(f"Could not load steering file {path}: {e}")
        return ""


def load_agent_steering(agent_name: str) -> str:
    """
    Load the full steering context for a given agent.

    Returns a formatted string containing:
    1. Agent-specific guardrails, parameters, skills, tools
    2. Shared environment and security context

    Returns empty string if steering directory is not found (graceful fallback).
    """
    steering_dir = _resolve_steering_dir()
    if not steering_dir:
        logger.warning("Steering directory not found — agents running without framework context")
        return ""

    # Determine which steering profile to load
    agent_key = agent_name.lower().replace("agent", "").replace("_", "").strip()
    profile = AGENT_STEERING_MAP.get(agent_key, "ai-engineer")

    sections: list[str] = []

    # Load agent-specific files
    agent_dir = steering_dir / "agents" / profile
    if agent_dir.is_dir():
        files_to_load = AGENT_FILES.get(profile, [])
        for filename in files_to_load:
            filepath = agent_dir / filename
            content = _load_file(filepath)
            if content:
                sections.append(content)

    # Load shared context (all agents get this)
    shared_dir = steering_dir / "shared"
    if shared_dir.is_dir():
        for filename in SHARED_FILES:
            filepath = shared_dir / filename
            # Skip if agent-specific version already loaded the same file
            if profile != "shared" or filename not in [f for f in AGENT_FILES.get(profile, [])]:
                content = _load_file(filepath)
                if content:
                    sections.append(content)

    # Load the agent prompt file from root steering
    prompt_map = {
        "devops": "devops-agent-prompt.md",
        "sre": "sre-agent-prompt.md",
        "ai-engineer": "ai-engineer-agent-prompt.md",
    }
    prompt_file = prompt_map.get(profile)
    if prompt_file:
        content = _load_file(steering_dir / prompt_file)
        if content:
            # Prepend the prompt as the primary identity
            sections.insert(0, content)

    if not sections:
        return ""

    # Load the global agent-rules (proposal format, hard rules, tone)
    agent_rules = _load_file(steering_dir / "agent-rules.md")
    if agent_rules:
        sections.append(agent_rules)

    return "\n\n---\n\n".join(sections)


def load_shared_steering() -> str:
    """Load only the shared steering context (for Darius or cross-agent use)."""
    steering_dir = _resolve_steering_dir()
    if not steering_dir:
        return ""

    sections: list[str] = []

    # Shared files
    shared_dir = steering_dir / "shared"
    if shared_dir.is_dir():
        for filename in SHARED_FILES:
            content = _load_file(shared_dir / filename)
            if content:
                sections.append(content)

    # Product context (high-level overview)
    product_ctx = _load_file(steering_dir / "product-context.md")
    if product_ctx:
        sections.insert(0, product_ctx)

    # Enterprise framework overview
    framework = _load_file(steering_dir / "enterprise-ai-agent-framework.md")
    if framework:
        sections.insert(0, framework)

    return "\n\n---\n\n".join(sections)


def load_profiles() -> dict[str, dict]:
    """Load all agent profiles from .kiro/agents/profiles/*.json."""
    import json

    profiles: dict[str, dict] = {}

    # Try multiple locations
    candidates = [
        os.environ.get("PROFILES_DIR", ""),
        "/app/.kiro/agents/profiles",
        str(Path(__file__).parent.parent.parent / ".kiro" / "agents" / "profiles"),
        "/Users/pktech_dev/Documents/MelaninTechnologies/.kiro/agents/profiles",
    ]

    profiles_dir = None
    for candidate in candidates:
        if candidate and Path(candidate).is_dir():
            profiles_dir = Path(candidate)
            break

    if not profiles_dir:
        return profiles

    for json_file in profiles_dir.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            name = data.get("name", json_file.stem)
            profiles[json_file.stem] = data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load profile {json_file}: {e}")

    return profiles
