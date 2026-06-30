# Task Templates
#
# YAML workflow definitions for repeatable multi-step pipelines.
# Used by both the orchestrator (Slack-triggered) and Darius (chain execution).
#
# Template format:
#   name: human-readable name
#   trigger: command that activates this template (e.g., "deploy-website")
#   params: optional parameters with defaults
#   steps: ordered list of actions
#
# Step types:
#   - agent: route to a specialist agent (generates proposal → approval)
#   - approve: human approval gate (Slack buttons)
#   - darius: Darius handles directly (analysis, planning)
#   - shell: execute a command (deploy-agent only)
#
# Human approval is ALWAYS required before any code is written or deployed.
# Templates skip the LLM planning step, not the approval step.
