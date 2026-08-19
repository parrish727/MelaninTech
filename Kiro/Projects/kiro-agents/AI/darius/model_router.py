"""
Model Router — selects the appropriate LLM based on task type and routing rules.

Reads _models.json for configuration. Falls back to defaults if config unavailable.

Usage:
    from AI.darius.model_router import select_model, get_model_config

    config = select_model("refactor the authentication system")
    # Returns: {"model": "anthropic/claude-sonnet-4-6", "max_tokens": 8192, "temperature": 0.3, "rule": "heavy_reasoning"}
"""
import os
import json
import logging

logger = logging.getLogger("darius.model_router")

_CONFIG = None
_CONFIG_PATH = os.environ.get("MODELS_CONFIG", None)

# Search paths for _models.json
_SEARCH_PATHS = [
    "/app/_models.json",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "_models.json"),
]


def _load_config() -> dict:
    """Load model routing config from _models.json."""
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG

    paths = [_CONFIG_PATH] + _SEARCH_PATHS if _CONFIG_PATH else _SEARCH_PATHS
    for path in paths:
        if path and os.path.isfile(path):
            try:
                with open(path) as f:
                    _CONFIG = json.load(f)
                logger.info(f"Model router config loaded from {path}")
                return _CONFIG
            except Exception as e:
                logger.warning(f"Failed to load {path}: {e}")

    # Fallback defaults
    _CONFIG = {
        "providers": {
            "anthropic": {
                "models": {
                    "sonnet": "claude-sonnet-4-6",
                    "haiku": "claude-haiku-4-5-20251001",
                }
            }
        },
        "routing_rules": [],
        "defaults": {
            "model": "anthropic/sonnet",
            "max_tokens": 8192,
            "temperature": 0.2,
            "fallback": "anthropic/haiku",
        },
    }
    return _CONFIG


def _resolve_model_id(model_ref: str) -> str:
    """Resolve a model reference (e.g. 'anthropic/sonnet') to the actual model ID."""
    config = _load_config()
    if "/" in model_ref:
        provider, model_name = model_ref.split("/", 1)
        provider_config = config.get("providers", {}).get(provider, {})
        models = provider_config.get("models", {})
        if model_name in models:
            return models[model_name]
    # Already a full model ID
    return model_ref


def select_model(task: str, task_type: str = None) -> dict:
    """
    Select the appropriate model for a task.

    Args:
        task: The task text to analyze
        task_type: Optional explicit type (planning, evaluation, classification, etc.)

    Returns:
        Dict with: model (full ID), max_tokens, temperature, rule (which rule matched)
    """
    config = _load_config()
    defaults = config.get("defaults", {})
    rules = config.get("routing_rules", [])

    task_lower = task.lower() if task else ""

    # If explicit task_type provided, match by name
    if task_type:
        for rule in rules:
            if rule.get("name") == task_type:
                return {
                    "model": _resolve_model_id(rule["model"]),
                    "max_tokens": rule.get("max_tokens", defaults.get("max_tokens", 8192)),
                    "temperature": rule.get("temperature", defaults.get("temperature", 0.2)),
                    "rule": rule["name"],
                }

    # Match by keywords
    for rule in rules:
        if rule.get("type") == "embedding":
            continue  # Skip embedding rules for text tasks
        keywords = rule.get("keywords", [])
        if any(kw in task_lower for kw in keywords):
            return {
                "model": _resolve_model_id(rule["model"]),
                "max_tokens": rule.get("max_tokens", defaults.get("max_tokens", 8192)),
                "temperature": rule.get("temperature", defaults.get("temperature", 0.2)),
                "rule": rule["name"],
            }

    # Default
    return {
        "model": _resolve_model_id(defaults.get("model", "anthropic/sonnet")),
        "max_tokens": defaults.get("max_tokens", 8192),
        "temperature": defaults.get("temperature", 0.2),
        "rule": "default",
    }


def get_embedding_model() -> str:
    """Get the model ID for embeddings."""
    config = _load_config()
    for rule in config.get("routing_rules", []):
        if rule.get("type") == "embedding":
            return _resolve_model_id(rule["model"])
    return "nomic-embed-text"


def get_cost_rate(model_id: str) -> dict:
    """Get cost rates per million tokens for a model."""
    config = _load_config()
    rates = config.get("cost_tracking", {}).get("rates_per_million", {})
    return rates.get(model_id, {"input": 3.0, "output": 15.0})


def list_available_models() -> list[dict]:
    """List all available models with their providers."""
    config = _load_config()
    models = []
    for provider_name, provider in config.get("providers", {}).items():
        if provider.get("status") == "future":
            continue
        for alias, model_id in provider.get("models", {}).items():
            models.append({
                "provider": provider_name,
                "alias": alias,
                "model_id": model_id,
                "type": provider.get("type", "api"),
            })
    return models
