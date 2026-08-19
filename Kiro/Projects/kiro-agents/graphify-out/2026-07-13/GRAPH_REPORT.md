# Graph Report - .  (2026-06-21)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 491 nodes · 769 edges · 38 communities (26 shown, 12 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 8 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3a01d7a6`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Approval & Proposal Handling|Approval & Proposal Handling]]
- [[_COMMUNITY_Core App & Contract Management|Core App & Contract Management]]
- [[_COMMUNITY_MCP Bridge JSON-RPC|MCP Bridge JSON-RPC]]
- [[_COMMUNITY_Darius Agent Orchestration|Darius Agent Orchestration]]
- [[_COMMUNITY_Contracts & Guardrails|Contracts & Guardrails]]
- [[_COMMUNITY_Docker Infrastructure Services|Docker Infrastructure Services]]
- [[_COMMUNITY_Agent Tool Definitions|Agent Tool Definitions]]
- [[_COMMUNITY_Frontend Package Dependencies|Frontend Package Dependencies]]
- [[_COMMUNITY_Base Agent & Model Guard|Base Agent & Model Guard]]
- [[_COMMUNITY_QA Agent & Testing|QA Agent & Testing]]
- [[_COMMUNITY_Python Backend Dependencies|Python Backend Dependencies]]
- [[_COMMUNITY_K8s Agent Deployments|K8s Agent Deployments]]
- [[_COMMUNITY_Vault Kill Switch Sync|Vault Kill Switch Sync]]
- [[_COMMUNITY_Dynamic Agent Spawning|Dynamic Agent Spawning]]
- [[_COMMUNITY_Security Watchdog Alerts|Security Watchdog Alerts]]
- [[_COMMUNITY_Playwright Visual Regression|Playwright Visual Regression]]
- [[_COMMUNITY_Agent App Factory|Agent App Factory]]
- [[_COMMUNITY_Deploy Pipeline|Deploy Pipeline]]
- [[_COMMUNITY_K8s Ingress & Certs|K8s Ingress & Certs]]
- [[_COMMUNITY_HUD Backend Dependencies|HUD Backend Dependencies]]
- [[_COMMUNITY_UX Audit Agent|UX Audit Agent]]
- [[_COMMUNITY_MCP Tool Calls|MCP Tool Calls]]
- [[_COMMUNITY_Code Agent Service|Code Agent Service]]
- [[_COMMUNITY_Scaffold Agent Service|Scaffold Agent Service]]
- [[_COMMUNITY_Backend Agent Service|Backend Agent Service]]
- [[_COMMUNITY_Client Onboarding Script|Client Onboarding Script]]
- [[_COMMUNITY_Package Type Config|Package Type Config]]
- [[_COMMUNITY_HUD Frontend Entry|HUD Frontend Entry]]
- [[_COMMUNITY_Slack Update Script|Slack Update Script]]
- [[_COMMUNITY_Cert Expiry Check|Cert Expiry Check]]
- [[_COMMUNITY_NPM Security Audit|NPM Security Audit]]
- [[_COMMUNITY_Container Scan Script|Container Scan Script]]
- [[_COMMUNITY_Agent Docker Network|Agent Docker Network]]
- [[_COMMUNITY_K8s Namespace|K8s Namespace]]

## God Nodes (most connected - your core abstractions)
1. `_db()` - 15 edges
2. `route()` - 13 edges
3. `K8s Agent Deployments` - 12 edges
4. `run_task()` - 11 edges
5. `create_app()` - 11 edges
6. `request_approval()` - 9 edges
7. `handle_approval()` - 9 edges
8. `store_conversation()` - 9 edges
9. `load_template()` - 9 edges
10. `_get_conn()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `Darius Agent Service` --references--> `Darius Agent`  [EXTRACTED]
  docker/docker-compose.yml → agents/darius_agent.py
- `K8s Agent Deployments` --references--> `Darius Agent`  [EXTRACTED]
  k8s/kiro-agents/04-agents.yaml → agents/darius_agent.py
- `Run QA Template` --references--> `Darius Agent`  [EXTRACTED]
  templates/run-qa.yaml → agents/darius_agent.py
- `run_template()` --calls--> `load_template()`  [EXTRACTED]
  AI/darius/agent.py → orchestrator/template_engine.py
- `run_template()` --calls--> `resolve_template()`  [EXTRACTED]
  AI/darius/agent.py → orchestrator/template_engine.py

## Import Cycles
- None detected.

## Communities (38 total, 12 thin omitted)

### Community 0 - "Approval & Proposal Handling"
Cohesion: 0.06
Nodes (56): _context_block(), execute_proposal(), handle_approval(), handle_modify_submit(), open_modify_modal(), Extract HTML from proposal and save as a preview file. Returns URL or None., Parse fenced code blocks with a file path comment on the first line.     Expecte, request_approval() (+48 more)

### Community 1 - "Core App & Contract Management"
Cohesion: 0.05
Nodes (46): _check_containers(), clients(), contracts(), contracts_darius(), costs(), create_contract(), darius(), dashboard() (+38 more)

### Community 2 - "MCP Bridge JSON-RPC"
Cohesion: 0.08
Nodes (32): BaseModel, call(), invoke_tool(), list_tools(), _next_id(), _parse_sse(), MCP Bridge — calls MCP sidecar servers via JSON-RPC 2.0 over HTTP/SSE. GitHub MC, Extract the first JSON-RPC result from an SSE stream. (+24 more)

### Community 3 - "Darius Agent Orchestration"
Cohesion: 0.11
Nodes (30): build_agent(), chain_tasks(), Darius Agent — smolagents ToolCallingAgent wired to Anthropic Claude.  Features:, Execute a sequence of agent tasks in order.     Each task dict: {"agent": "front, Execute a YAML template by trigger name.     Resolves params, then runs chain_ta, Run a task through Darius and optionally persist the session., Replay a session from a specific turn. Re-runs each user turn through the agent., replay_session() (+22 more)

### Community 4 - "Contracts & Guardrails"
Cohesion: 0.11
Nodes (29): Guardrail Check Hook, check(), consume_ticket(), _load(), Returns {"allowed": bool, "reason": str, "type": str}, Increments usage ticket count for usage-based contracts., Register or update a support contract., register() (+21 more)

### Community 5 - "Docker Infrastructure Services"
Cohesion: 0.09
Nodes (31): HTC App (Held Together Caregiving), nomic-embed-text (Ollama model), Cert Monitor Service, Certbot Service, ChromaDB Service, Cloudflare DDNS Service, Fail2ban Service, HTC Backend Service (+23 more)

### Community 6 - "Agent Tool Definitions"
Cohesion: 0.11
Nodes (18): AgentDispatchTool, _confirm(), _discover_mcp_tools(), GitTool, _guard(), ListDirTool, MCPTool, _needs_confirmation() (+10 more)

### Community 7 - "Frontend Package Dependencies"
Cohesion: 0.11
Nodes (17): dependencies, lucide-react, react, react-dom, devDependencies, tailwindcss, @tailwindcss/vite, typescript (+9 more)

### Community 8 - "Base Agent & Model Guard"
Cohesion: 0.21
Nodes (13): _cache_get(), _cache_key(), _cache_set(), _complete(), _get_redis(), _guard_model(), _log_usage(), Log LLM usage to database for cost tracking. (+5 more)

### Community 10 - "QA Agent & Testing"
Cohesion: 0.17
Nodes (13): _check_endpoint(), QA Agent — runs automated tests and verifies builds before deployment., Run QA for a project. Called by orchestrator after code changes., Run full QA suite for a project., _run_cmd(), run_qa(), task(), Melanin Tech Website Project (+5 more)

### Community 11 - "Python Backend Dependencies"
Cohesion: 0.15
Nodes (12): anthropic, docker SDK, fastapi, httpx, openai, pgvector, psycopg2-binary, python-dotenv (+4 more)

### Community 12 - "K8s Agent Deployments"
Cohesion: 0.20
Nodes (9): Darius Agent, Anthropic Claude (claude-sonnet-4-6), Darius Agent Service, File Agent Service, K8s Agent Deployments, K8s Infrastructure (Postgres + Ollama), K8s MCP Sidecars, K8s PVCs (+1 more)

### Community 13 - "Vault Kill Switch Sync"
Cohesion: 0.31
Nodes (10): disengage_kill_switch(), engage_kill_switch(), is_locked(), log(), Check if kill switch is engaged., KILL SWITCH — immediately disconnects secrets from all services.     1. Backs up, Restore .env from backup and remove lock., Pull secrets from Vaultwarden and write .env (placeholder — requires bw CLI auth (+2 more)

### Community 14 - "Dynamic Agent Spawning"
Cohesion: 0.25
Nodes (10): _client(), kill_agent(), kill_all(), list_active(), Agent Spawn Template — dynamically spin up/down agent instances.  Usage:     fro, Kill all dynamic agents, optionally filtered by skill or project., List all active dynamic agent containers., Spin up one or more agent containers with a specific skill loaded.      Args: (+2 more)

### Community 15 - "Security Watchdog Alerts"
Cohesion: 0.36
Nodes (9): Security Watchdog Service, check_docker_socket_access(), check_fail2ban_bans(), check_secret_leaks_in_logs(), log(), main(), Post violation alert to Slack with approval buttons. Returns message ts., run_checks() (+1 more)

### Community 16 - "Playwright Visual Regression"
Cohesion: 0.36
Nodes (9): Path, _b64(), diff(), extract(), Playwright MCP — visual regression & screenshot service for the UXUIAgent.  Endp, Intercept network requests to find fonts used by a JS-rendered page., Extract fonts and CSS from a JS-rendered page by intercepting network requests., _screenshot() (+1 more)

### Community 17 - "Agent App Factory"
Cohesion: 0.28
Nodes (6): create_app(), load_skill(), Load a skill.md file and return its content as a system prompt.     Falls back t, Create a FastAPI app for an agent.     system_prompt can be:       - A string (b, handle(), Support Agent Service

### Community 18 - "Deploy Pipeline"
Cohesion: 0.28
Nodes (7): DockerClient, deploy_pipeline(), deploy_to_production(), Auto-deploy pipeline: rebuilds testing then staging after proposal approval. Aft, Called when production approval is clicked., Rebuild testing then staging, then post production approval., _rebuild()

### Community 19 - "K8s Ingress & Certs"
Cohesion: 0.25
Nodes (8): Let's Encrypt Production ClusterIssuer, Let's Encrypt Staging ClusterIssuer, K8s AWS Migration Guide, K8s Bootstrap (nginx-ingress + cert-manager), Client Site Template, Melanin Website Ingress, Melanin Website K8s Manifests, Client Network Policy Template

### Community 20 - "HUD Backend Dependencies"
Cohesion: 0.25
Nodes (8): docker SDK (HUD), fastapi (HUD), httpx (HUD), kubernetes (HUD), psycopg2-binary (HUD), python-jose (HUD), HUD Backend requirements.txt, uvicorn (HUD)

### Community 21 - "UX Audit Agent"
Cohesion: 0.40
Nodes (4): Melanin Technologies — Design System & Specification Loaded statically into agen, _audit_screenshot(), handle(), Take a visual audit of the live site and return a summary.

### Community 22 - "MCP Tool Calls"
Cohesion: 0.50
Nodes (4): call_tool(), fetch_mcp_context(), Call any MCP skill by name. Returns parsed JSON or None on failure., Fetch project context from MCP server to prepend to the LLM prompt.

## Knowledge Gaps
- **64 isolated node(s):** `ToolCallingAgent`, `check-cert-expiry.sh script`, `HTTPAuthorizationCredentials`, `WebSocket`, `type` (+59 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Guardrail Check Hook` connect `Contracts & Guardrails` to `Scaffold Agent Service`, `Docker Infrastructure Services`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Why does `Sync Steering Hook` connect `Contracts & Guardrails` to `Base Agent & Model Guard`, `Approval & Proposal Handling`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Why does `resolve_template()` connect `Contracts & Guardrails` to `Darius Agent Orchestration`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **What connects `ToolCallingAgent`, `Darius Agent — smolagents ToolCallingAgent wired to Anthropic Claude.  Features:`, `Run a task through Darius and optionally persist the session.` to the rest of the system?**
  _156 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Approval & Proposal Handling` be split into smaller, more focused modules?**
  _Cohesion score 0.06433566433566433 - nodes in this community are weakly interconnected._
- **Should `Core App & Contract Management` be split into smaller, more focused modules?**
  _Cohesion score 0.05411764705882353 - nodes in this community are weakly interconnected._
- **Should `MCP Bridge JSON-RPC` be split into smaller, more focused modules?**
  _Cohesion score 0.07557354925775979 - nodes in this community are weakly interconnected._