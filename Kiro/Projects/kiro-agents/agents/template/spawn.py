"""
Agent Spawn Template — dynamically spin up/down agent instances.

Usage:
    from agents.template.spawn import spawn_agent, kill_agent, list_active

    # Spin up a frontend agent for a specific project
    container_id = spawn_agent("frontend", project="orthoflow", replicas=2)

    # Kill when done
    kill_agent(container_id)

    # List active dynamic agents
    active = list_active()
"""
import os
import docker

_DOCKER_CLIENT = None
_NETWORK = "docker_agent-net"
_SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")
_BASE_IMAGE = os.environ.get("AGENT_BASE_IMAGE", "docker-scaffold-agent")  # any agent image works


def _client():
    global _DOCKER_CLIENT
    if _DOCKER_CLIENT is None:
        _DOCKER_CLIENT = docker.from_env()
    return _DOCKER_CLIENT


def spawn_agent(
    skill: str,
    project: str = "default",
    replicas: int = 1,
    env_overrides: dict = None,
) -> list[str]:
    """
    Spin up one or more agent containers with a specific skill loaded.

    Args:
        skill: Name of the skill (matches skills/{skill}.skill.md)
        project: Project context for the agent
        replicas: Number of instances to spawn
        env_overrides: Additional env vars to pass

    Returns:
        List of container IDs
    """
    skill_path = os.path.join(_SKILLS_DIR, f"{skill}.skill.md")
    if not os.path.isfile(skill_path):
        raise ValueError(f"Skill not found: {skill_path}")

    client = _client()
    env = {
        "PROJECTS_BASE": "/app/Projects",
        "SKILL_NAME": skill,
        "SKILL_FILE": f"/app/agents/skills/{skill}.skill.md",
        "PROJECT": project,
    }
    if env_overrides:
        env.update(env_overrides)

    container_ids = []
    for i in range(replicas):
        name = f"dynamic-{skill}-{project}-{i}"
        # Remove existing container with same name
        try:
            old = client.containers.get(name)
            old.remove(force=True)
        except docker.errors.NotFound:
            pass

        container = client.containers.run(
            image=_BASE_IMAGE,
            name=name,
            detach=True,
            network=_NETWORK,
            environment=env,
            labels={
                "managed-by": "darius-spawn",
                "skill": skill,
                "project": project,
            },
            restart_policy={"Name": "unless-stopped"},
        )
        container_ids.append(container.id[:12])

    return container_ids


def kill_agent(container_id: str) -> bool:
    """Stop and remove a dynamic agent container."""
    try:
        client = _client()
        container = client.containers.get(container_id)
        container.stop(timeout=5)
        container.remove()
        return True
    except Exception:
        return False


def kill_all(skill: str = None, project: str = None) -> int:
    """Kill all dynamic agents, optionally filtered by skill or project."""
    client = _client()
    filters = {"label": "managed-by=darius-spawn"}
    if skill:
        filters["label"] = [filters["label"], f"skill={skill}"]
    if project:
        filters["label"] = [filters["label"], f"project={project}"]

    containers = client.containers.list(filters=filters)
    count = 0
    for c in containers:
        c.stop(timeout=5)
        c.remove()
        count += 1
    return count


def list_active() -> list[dict]:
    """List all active dynamic agent containers."""
    client = _client()
    containers = client.containers.list(filters={"label": "managed-by=darius-spawn"})
    return [
        {
            "id": c.id[:12],
            "name": c.name,
            "skill": c.labels.get("skill", "unknown"),
            "project": c.labels.get("project", "unknown"),
            "status": c.status,
        }
        for c in containers
    ]
