# Graph Report - .  (2026-07-19)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1465 nodes · 2234 edges · 115 communities (93 shown, 22 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 102 edges (avg confidence: 0.68)
- Token cost: 7,364 input · 1,117 output

## Graph Freshness
- Built from commit: `58834bfa`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Agent Contracts & Guardrails
- Darius Agent Core
- MCP Bridge & Sidecar RPC
- MCP Sidecar Registry
- Agent Skills & Tools
- Backend Data & Charts
- React HUD Frontend
- Agent Tools & Gateway
- Tickets & Watchdog
- Autonomous Background Loop
- Frontend Dependencies
- Tool & Integration Registry
- CLI & Session Replay
- GSC & Keyword SEO Pipeline
- Scoped RAG Namespaces
- SEO Analysis Agent
- Slack Event Handlers
- Specialist Agent Backends
- Task Planner & DAG
- Deploy Webhook & SRE
- FastAPI Task Server
- SEO Self-Improvement Loop
- File-Tree Workflow Engine
- Redis Shared Memory
- Swarm Agent Coordination
- QA Agent & Testing
- Agent Skills & Guardrails Config
- Skill Refinement Engine
- HUD Proxy & Caching
- GSC Connector
- Keyword Research Tool
- Delta Context Executor
- MCP Gateway Tools
- Base Agent Utilities
- Playwright Visual Auditing
- Integration Base Connector
- Swarm Architecture Overview
- Knowledge Graph Builder
- Output Evaluator
- SEO Auto-Ticket Pipeline
- Deploy & Approval Agent
- Model Router
- Agent Swarm Execution
- Steering Context Loader
- Trace Analyzer & Improvement
- Swarm Agent Execution Unit
- LLM Model Pricing
- Python Dependencies
- DAG Executor Tests
- Environment Setup Script
- SRE Background Monitors
- Gmail Connector
- Dynamic Agent Spawning
- Evaluator Unit Tests
- Integration Connectors Registry
- SERP Position Tracker
- Training Data Export
- Vault & Kill Switch
- Notion Connector
- Model Routing Config
- Security Watchdog
- Evaluator Retry Logic
- Context Build Tests
- Kubernetes Ingress & Certs
- HUD Backend Dependencies
- LLM Observability Dashboard
- Google OAuth Flow
- Google Calendar Connector
- Anthropic Model Config
- Darius v2 Tests
- Docs Graph Parser
- Ollama Provider Config
- UX/UI Design Agent
- SRE Agent
- Integration Tests
- Compliance & Security Docs
- Client Auth & TOTP
- Integration Tool Wrapper
- Local Model Config
- Credit Budget Guard
- DBA Agent
- Local Model Training Plan
- LLM Default Parameters
- Coordination Signal Queue
- Infrastructure Status Query
- WebSocket Live Data
- Workflow Listing
- Connector Actions Interface
- HUD Monitoring Watchdog
- Kubernetes Infrastructure
- Swarm Package Init
- Completed Agents Listing
- Project System Manifest
- Certificate Expiry Check
- SRE External Status View
- Frontend Package Config
- SEO Pipeline Architecture
- Client Onboarding Script
- Slack Update Poster
- NPM Security Audit Script
- Container Scanning Script
- File Agent Skill
- SEO AEO Agent Skill
- Novu Notification Stack
- Penetration Test Procedure
- HUD Frontend HTML
- Client Hosting Platform
- Kubernetes Namespace Config
- Kubernetes Manifests Docs
- Task Templates Docs
- Output Completeness Check

## God Nodes (most connected - your core abstractions)
1. `SharedMemory` - 33 edges
2. `_db()` - 27 edges
3. `run_task()` - 25 edges
4. `log_trace()` - 20 edges
5. `AgentSwarm` - 19 edges
6. `BaseConnector` - 18 edges
7. `DeltaExecutor` - 17 edges
8. `GmailConnector` - 17 edges
9. `build_context()` - 16 edges
10. `SkillRefiner` - 16 edges

## Surprising Connections (you probably didn't know these)
- `build_context()` --calls--> `recall()`  [INFERRED]
  AI/darius/context.py → orchestrator/scoped_rag.py
- `start()` --indirect_call--> `_loop()`  [INFERRED]
  orchestrator/watchdog.py → AI/darius/swarm/autonomous.py
- `RPCRequest` --uses--> `GmailConnector`  [INFERRED]
  orchestrator/mcp_gateway.py → integrations/gmail.py
- `RPCRequest` --uses--> `GSCConnector`  [INFERRED]
  orchestrator/mcp_gateway.py → integrations/seo/gsc.py
- `Docker Compose Services` --references--> `Shared Environments Config`  [INFERRED]
  docker/docker-compose.yml → .kiro/steering/shared/Environments.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Agent Skill + Tools Pairs (all inherit shared.tools)** — agents_skills_shared_tools, agents_skills_backend_tools, agents_skills_frontend_tools, agents_skills_qa_tools, agents_skills_deploy_tools, agents_skills_scaffold_tools, agents_skills_file_tools, agents_skills_support_tools, agents_skills_seo_tools, agents_skills_code_tools, agents_skills_dba_tools, agents_skills_uxui_tools [EXTRACTED 1.00]
- **Darius v3 Execution Components (DeltaExecutor, AgentSwarm, SwarmAgent, SharedMemory, RedisState)** — ai_darius_delta_executor, ai_darius_agent_swarm, ai_darius_swarm_agent, ai_darius_redis_state, ai_darius_shared_memory [EXTRACTED 0.95]
- **SEO Improvement Workflow Pipeline (collect → analyze → generate → deploy → validate)** — workflows_seo_improve_steps_01_collect_data, workflows_seo_improve_steps_02_analyze, workflows_seo_improve_steps_03_generate_fix, workflows_seo_improve_steps_04_preview_deploy, workflows_seo_improve_steps_05_validate [EXTRACTED 0.98]

## Communities (115 total, 22 thin omitted)

### Community 0 - "Agent Contracts & Guardrails"
Cohesion: 0.05
Nodes (45): DockerClient, Guardrail Check Hook, Sync Steering Hook, check(), consume_ticket(), _load(), Returns {"allowed": bool, "reason": str, "type": str}, Increments usage ticket count for usage-based contracts. (+37 more)

### Community 1 - "Darius Agent Core"
Cohesion: 0.08
Nodes (46): build_agent(), _check_ollama_health(), Darius Agent — smolagents ToolCallingAgent wired to Anthropic Claude.  Features, Quick check if Ollama is reachable., Build a Darius agent with the appropriate model.      Args:         task: The ta, Run a task through Darius with planning, execution, evaluation, and compressed c, Select model based on task complexity, source, and override.      Tiers (cloud):, run_task() (+38 more)

### Community 2 - "MCP Bridge & Sidecar RPC"
Cohesion: 0.07
Nodes (39): call(), invoke_tool(), list_tools(), _next_id(), _parse_sse(), MCP Bridge — calls MCP sidecar servers via JSON-RPC 2.0 over HTTP/SSE. GitHub MC, Extract the first JSON-RPC result from an SSE stream., Send a JSON-RPC request to a named MCP sidecar. Returns the result dict. (+31 more)

### Community 3 - "MCP Sidecar Registry"
Cohesion: 0.04
Nodes (45): description, protocol, status, tools, url, description, protocol, status (+37 more)

### Community 4 - "Agent Skills & Tools"
Cohesion: 0.06
Nodes (37): Backend Agent Skill, Backend Agent Tools, Code Agent Skill, Code Agent Tools, DBA Agent Skill, DBA Agent Tools, Deploy Agent Skill, Deploy Agent Tools (+29 more)

### Community 5 - "Backend Data & Charts"
Cohesion: 0.09
Nodes (31): charts_agents(), charts_contracts(), charts_executive(), charts_sre(), charts_tickets(), contracts(), costs(), create_contract() (+23 more)

### Community 6 - "React HUD Frontend"
Cohesion: 0.08
Nodes (21): react, Agents(), ContractsTab(), DariusMarkdown(), Dashboard(), GlobalDarius(), GovernanceTab(), GraphData (+13 more)

### Community 7 - "Agent Tools & Gateway"
Cohesion: 0.10
Nodes (21): AgentDispatchTool, _confirm(), _discover_mcp_tools(), GatewayTool, GitTool, _guard(), ListDirTool, _load_registry_descriptions() (+13 more)

### Community 8 - "Tickets & Watchdog"
Cohesion: 0.12
Nodes (27): Extract HTML from proposal and save as a preview file. Returns URL or None., request_approval(), _save_preview(), _get_conn(), get_stuck_tickets(), increment_attempts(), open_ticket(), Increment attempt counter and return new count. (+19 more)

### Community 9 - "Autonomous Background Loop"
Cohesion: 0.11
Nodes (28): _claim_ticket(), _complete_ticket(), _execute_ticket(), _fail_ticket(), _get_open_tickets(), _get_redis(), _heartbeat(), _is_kill_switched() (+20 more)

### Community 10 - "Frontend Dependencies"
Cohesion: 0.07
Nodes (27): dependencies, lucide-react, react-dom, react-force-graph-2d, recharts, devDependencies, tailwindcss, @tailwindcss/vite (+19 more)

### Community 11 - "Tool & Integration Registry"
Cohesion: 0.07
Nodes (26): agent_tools, description, tools, description, integrations, connectors, description, internal_tools (+18 more)

### Community 12 - "CLI & Session Replay"
Cohesion: 0.12
Nodes (23): Replay a session from a specific turn. Re-runs each user turn through the agent., replay_session(), _is_conversational(), main(), Darius CLI — interactive terminal entrypoint. Usage:   python -m AI.darius.cli, Run the self-improvement cycle., Execute a task using the specified engine., _run_improve() (+15 more)

### Community 13 - "GSC & Keyword SEO Pipeline"
Cohesion: 0.14
Nodes (20): Google Search Console Connector — pulls query and page performance data.  Uses t, Keyword Research Tool — discovers keywords and competitive intelligence via Sear, _get_conn(), get_keywords(), get_position_history(), SEO Pipeline — Data Model (Postgres)  Tables:   seo_sites          — registered, Register a site for SEO tracking., Bulk insert GSC query data for a date range. (+12 more)

### Community 14 - "Scoped RAG Namespaces"
Cohesion: 0.12
Nodes (24): clear_namespace(), _embed(), _get_conn(), get_namespace_stats(), list_namespaces(), Scoped RAG — per-project/workflow vector namespaces.  Each project and workflow, Recall relevant context from a namespace (or global).      Args:         query:, Recall context scoped to a specific workflow. (+16 more)

### Community 15 - "SEO Analysis Agent"
Cohesion: 0.13
Nodes (16): SEO Analysis Agent — interprets collected data and identifies improvement opport, Find keywords at positions 11-20 — quick wins to push to page 1., Find queries with high impressions but below-average CTR., Find question-type queries we're not adequately addressing., Report significant position changes (both up and down)., Shorten a URL to just the path., Analyzes SEO data and produces actionable findings., Run all analysis passes and store findings.         Returns list of new findings (+8 more)

### Community 16 - "Slack Event Handlers"
Cohesion: 0.14
Nodes (19): handle_approval(), handle_modify_submit(), open_modify_modal(), _estimate_eta(), handle_internal_task(), handle_mention(), handle_message(), handle_status() (+11 more)

### Community 17 - "Specialist Agent Backends"
Cohesion: 0.11
Nodes (12): create_app(), load_skill(), Load a skill.md file and return its content as a system prompt.     Falls back t, Create a FastAPI app for an agent.     system_prompt can be:       - A string (b, Code Agent — general-purpose code generation and refactoring., File Agent — file system operations specialist., handle(), Scaffold Agent — project bootstrapping and initialization. (+4 more)

### Community 18 - "Task Planner & DAG"
Cohesion: 0.12
Nodes (16): _is_complex_task(), plan_task(), PlannerTool, Tool, _quick_classify(), Darius Planner — decomposes tasks into execution DAGs.  The PlannerTool is invok, Fast keyword-based agent classification (no LLM call)., Determine if a task needs planning or can be executed directly. (+8 more)

### Community 19 - "Deploy Webhook & SRE"
Cohesion: 0.11
Nodes (19): _handle_ci_failure(), _identify_project(), BaseHTTPRequestHandler, Deploy Webhook — receives notifications from Watchtower and GitHub Actions, then, Handle CI pipeline failures — diagnose, alert, and attempt auto-fix.      Flow:, Post-deploy SRE health verification. Runs after QA passes., Simple HTTP handler for deploy webhooks., Suppress default access logs — use structured logging instead. (+11 more)

### Community 20 - "FastAPI Task Server"
Cohesion: 0.12
Nodes (20): chain_tasks(), Execute a sequence of agent tasks — now powered by the DAG executor.      Each t, Execute a YAML template by trigger name.     Resolves params, then runs chain_ta, run_template(), chain(), chat(), Darius FastAPI server — receives tasks from the orchestrator router. Endpoints:, Execute a complex task using the Agent Swarm (v3 engine).     Decomposes into pa (+12 more)

### Community 21 - "SEO Self-Improvement Loop"
Cohesion: 0.13
Nodes (21): build_frontend_task(), check_regressions(), load_design_system(), post_improvement_summary(), Self-Improvement Loop — connects SEO findings to the frontend agent with visual, Take baseline screenshots of production site., Take screenshots of preview deployment., Run Lighthouse audit on the preview deployment. (+13 more)

### Community 22 - "File-Tree Workflow Engine"
Cohesion: 0.12
Nodes (20): create_workflow(), _default_tools_for_agent(), _load_file_tree_workflow(), load_workflow(), _load_workflow_meta(), migrate_template(), Path, File-Tree Workflow Engine — workflows as directories, not just YAML.  Structure: (+12 more)

### Community 23 - "Redis Shared Memory"
Cohesion: 0.10
Nodes (10): Accumulate token usage for this task., Get total token usage for this task., Set task status: running, complete, failed., Emit a coordination signal for other agents to observe., Read another agent's compressed summary., Explicitly remove all keys for this task (normally TTL handles this)., Redis-backed shared memory for a single task execution.     All operations are a, Save a completed step's results. (+2 more)

### Community 24 - "Swarm Agent Coordination"
Cohesion: 0.12
Nodes (10): Get all step summaries in order., Get the full result for a specific step (for when summary isn't enough)., How many steps have completed., Declare that an agent intends to modify a file. Used for conflict detection., Get all detected file conflicts., Read another agent's full result (use sparingly — large)., Check if another agent has completed., Set a value (auto-serializes dicts/lists to JSON). (+2 more)

### Community 25 - "QA Agent & Testing"
Cohesion: 0.15
Nodes (17): _auto_seed_if_empty(), _check_container_health(), _check_endpoint(), _get_auth_token(), list_projects(), QA Agent — automated testing, build verification, and security scanning.  Compan, Login and get a JWT for authenticated testing., Check if clinical data exists; if empty, attempt to seed via the backend contain (+9 more)

### Community 26 - "Agent Skills & Guardrails Config"
Cohesion: 0.12
Nodes (19): DariusHUD Skill, DariusHUD Tools, Darius Agent Skill, Darius Agent Tools, External SRE Agent Skill, Internal Operations Skill, Internal SRE Agent Skill, Integration Engine (+11 more)

### Community 27 - "Skill Refinement Engine"
Cohesion: 0.13
Nodes (10): Skill Refinement Engine — Proposes prompt/skill updates based on failure pattern, Generate a proposal for a skill gap (task type that repeatedly fails)., Propose switching a model tier based on performance data., Map a tool/phase to the most relevant skill file., Read a file's content., Format proposals for human-readable output (Slack/HUD)., Proposes skill/prompt refinements based on failure analysis.     All proposals a, Generate refinement proposals from analyzer insights.          Args: (+2 more)

### Community 28 - "HUD Proxy & Caching"
Cohesion: 0.14
Nodes (19): _build_tab_context(), contracts_darius(), darius_global(), _get_hud_redis(), governance_darius(), _hud_cache_get(), _hud_cache_key(), _hud_cache_set() (+11 more)

### Community 29 - "GSC Connector"
Cohesion: 0.15
Nodes (10): GSCConnector, Query Search Analytics API.          Args:             site_url: The GSC propert, Collect the last 28 days of GSC data for a domain and store it.         Also aut, Verify GSC connection is working., Google Search Console API connector., Load OAuth tokens from credentials directory., Get valid access token, refreshing if expired., Refresh the OAuth access token. (+2 more)

### Community 30 - "Keyword Research Tool"
Cohesion: 0.14
Nodes (12): _classify_keyword(), _extract_domain(), KeywordResearcher, For each keyword, find which competitor pages rank in top positions.         Ret, Find keywords where our site doesn't appear in the top 20 results.         These, Run a full keyword discovery session.          If no seeds provided, uses existi, Extract domain from URL., Auto-classify a keyword into a category. (+4 more)

### Community 31 - "Delta Context Executor"
Cohesion: 0.16
Nodes (10): DeltaExecutor, DeltaExecutor — Multi-step task execution with delta context management.  Instea, Decompose task into steps using the light model (cheap, fast)., Build the prompt for a single step — minimal, focused., Compress a step result to ~200 tokens using Haiku (cheap)., Combine step results into a final output., Single LLM call with token tracking., Log the execution to darius_traces for observability. (+2 more)

### Community 32 - "MCP Gateway Tools"
Cohesion: 0.12
Nodes (7): BaseModel, list_tools(), Custom MCP Gateway — exposes Slack, Google, Cloudflare, and Docker as MCP-compat, JSON-RPC 2.0 endpoint — route to the appropriate tool handler., REST endpoint for tool discovery., rpc(), RPCRequest

### Community 33 - "Base Agent Utilities"
Cohesion: 0.15
Nodes (14): _cache_get(), _cache_key(), _cache_set(), call_tool(), fetch_mcp_context(), _get_redis(), _log_failure(), _log_trace() (+6 more)

### Community 34 - "Playwright Visual Auditing"
Cohesion: 0.17
Nodes (15): audit_lighthouse(), audit_visual(), _b64(), diff(), extract(), Path, Playwright + Lighthouse MCP — visual awareness & quality scoring for agents.  En, Screenshot a URL at desktop, tablet, and mobile breakpoints. (+7 more)

### Community 35 - "Integration Base Connector"
Cohesion: 0.18
Nodes (8): ABC, BaseConnector, Integration Engine — Base connector class. All connectors (Gmail, Notion, Calend, Base class for all integration connectors., Args:             client_id: Unique client identifier (maps to Vaultwarden folde, Override per provider (Google, Microsoft, etc.), Make authenticated HTTP request with retry., Verify the connection is working.

### Community 36 - "Swarm Architecture Overview"
Cohesion: 0.15
Nodes (12): AgentSwarm Class, Darius v3 Architecture: Delta Context + Agent Swarm, DeltaExecutor Class, RedisState (Delta Executor State), SharedMemory (Swarm Redis Layer), SwarmAgent — An ephemeral execution unit in the Darius Agent Swarm.  Unlike Dock, _get_redis(), SharedMemory — Redis-backed state layer for the DeltaExecutor and future Agent S (+4 more)

### Community 37 - "Knowledge Graph Builder"
Cohesion: 0.13
Nodes (16): _build_unified_graph(), _get_agent_nodes(), _get_service_nodes(), graph_data(), _graph_embed(), graph_index(), graph_search(), _init_graph_table() (+8 more)

### Community 38 - "Output Evaluator"
Cohesion: 0.21
Nodes (11): _check_guardrails(), evaluate_output(), EvaluatorTool, _llm_evaluate(), _log_evaluation(), Tool, Darius Evaluator — scores specialist agent output and triggers revision loops., Evaluate specialist agent output.      Returns:         {             "passed": (+3 more)

### Community 39 - "SEO Auto-Ticket Pipeline"
Cohesion: 0.20
Nodes (13): get_findings(), get_site(), Get analysis findings by status., _build_task(), generate_tickets(), post_weekly_summary(), SEO Auto-Ticket System — converts analysis findings into actionable tickets.  Fl, Build a task description from a template and finding data. (+5 more)

### Community 40 - "Deploy & Approval Agent"
Cohesion: 0.25
Nodes (12): _complete(), _guard_model(), select_model(), _deploy_service(), Build and restart a known Docker service using the SDK — no compose file path ne, task(), _context_block(), execute_proposal() (+4 more)

### Community 41 - "Model Router"
Cohesion: 0.22
Nodes (13): get_cost_rate(), get_embedding_model(), list_available_models(), _load_config(), Model Router — selects the appropriate LLM based on task type and routing rules., Get the model ID for embeddings., Get cost rates per million tokens for a model., List all available models with their providers. (+5 more)

### Community 42 - "Agent Swarm Execution"
Cohesion: 0.14
Nodes (7): Use the coordinator model to decompose the task., Create SwarmAgent instances from decomposition specs., Dynamically compose a skill prompt for this agent., Group agents into execution waves based on dependencies.         Wave 0: agents, Execute a wave of agents in parallel., Combine all agent results into a coherent final output., Full swarm execution:         1. Decompose task into agent assignments         2

### Community 43 - "Steering Context Loader"
Cohesion: 0.23
Nodes (12): load_agent_steering(), _load_file(), load_profiles(), load_shared_steering(), Path, Steering Loader — Bridges .kiro/steering/ framework into the agent runtime.  Loa, Load only the shared steering context (for Darius or cross-agent use)., Load all agent profiles from .kiro/agents/profiles/*.json. (+4 more)

### Community 44 - "Trace Analyzer & Improvement"
Cohesion: 0.18
Nodes (12): improve(), _post_improvement_report(), Run the self-improvement cycle:     1. Analyze traces for patterns     2. Genera, Post improvement cycle results to Slack., analyze(), _generate_recommendations(), _get_conn(), Trace Analyzer — Extracts actionable patterns from Darius execution history.  An (+4 more)

### Community 45 - "Swarm Agent Execution Unit"
Cohesion: 0.19
Nodes (7): Read summaries from other agents that have already completed., Build the execution prompt with peer context., Compress result to a brief summary for other agents to consume., Serialize agent state for reporting., A single ephemeral agent in the swarm.      Reads from shared memory, executes i, Execute this agent's task. Reads shared memory, produces result., SwarmAgent

### Community 46 - "LLM Model Pricing"
Cohesion: 0.15
Nodes (13): input, output, input, output, input, output, rates_per_million, input (+5 more)

### Community 47 - "Python Dependencies"
Cohesion: 0.15
Nodes (12): anthropic, docker SDK, fastapi, httpx, openai, pgvector, psycopg2-binary, python-dotenv (+4 more)

### Community 48 - "DAG Executor Tests"
Cohesion: 0.20
Nodes (8): Group steps into levels for parallel execution.     Level 0: no dependencies (ru, _topological_levels(), Tests for AI.darius.evaluator, Steps without dependencies should be grouped into the same level., Sequential dependencies should produce one-step-per-level., Circular dependencies should not deadlock — force execution., DAG execution should call agents and collect results., TestDAGExecutor

### Community 49 - "Environment Setup Script"
Cohesion: 0.32
Nodes (10): check_deps(), create_env(), error(), fill_secrets(), log(), main(), replace_if_empty(), sed_inplace() (+2 more)

### Community 50 - "SRE Background Monitors"
Cohesion: 0.23
Nodes (12): _check_containers(), _check_credit_budget(), _check_endpoint_health(), lifespan(), Check key service endpoints every 5 min via the FULL CHAIN (through nginx). Aler, Triage CEO inbox and post summary to Slack every morning., Background thread: check container health every 60s, alert on failures, store sn, Check if LLM spend is approaching monthly budget. Alert Slack at 80%. (+4 more)

### Community 51 - "Gmail Connector"
Cohesion: 0.18
Nodes (5): GmailConnector, Refresh Google OAuth token., Add label to message., _google_gmail_read(), _google_gmail_send()

### Community 52 - "Dynamic Agent Spawning"
Cohesion: 0.25
Nodes (10): _client(), kill_agent(), kill_all(), list_active(), Agent Spawn Template — dynamically spin up/down agent instances.  Usage:     fro, Kill all dynamic agents, optionally filtered by skill or project., List all active dynamic agent containers., Spin up one or more agent containers with a specific skill loaded.      Args: (+2 more)

### Community 53 - "Evaluator Unit Tests"
Cohesion: 0.20
Nodes (7): _check_structural_validity(), Fast pre-check — does the output have code blocks with file paths?, Blocked patterns should cause immediate failure., Properly formatted code blocks should pass structural validation., Code blocks without file paths should fail structural check., evaluate_with_retries should notify Slack after max failures., TestEvaluator

### Community 54 - "Integration Connectors Registry"
Cohesion: 0.24
Nodes (6): Gmail Connector — read, send, label, search emails., Google Calendar Connector — create, list, update events., IntegrationRegistry, Central registry of all available connectors., Notion Connector — create pages, query databases, update properties., Integration Tool for Darius — wraps all connectors into a single tool interface.

### Community 55 - "SERP Position Tracker"
Cohesion: 0.20
Nodes (7): _classify_change(), Get keywords with significant position changes.          Args:             direc, Classify a position change into a category., Tracks SERP positions for a domain's keyword list., Check where our domain ranks for a keyword.          Returns:             {, Check positions for all active keywords and store results.         Compares with, SERPTracker

### Community 56 - "Training Data Export"
Cohesion: 0.27
Nodes (10): export_traces(), format_conversation(), format_jsonl(), get_conn(), group_by_task(), main(), Format as JSONL training pairs.     Each line: {"input": task_description, "reas, Format as conversation-style training data (system/user/assistant turns).     Co (+2 more)

### Community 57 - "Vault & Kill Switch"
Cohesion: 0.31
Nodes (10): disengage_kill_switch(), engage_kill_switch(), is_locked(), log(), Check if kill switch is engaged., KILL SWITCH — immediately disconnects secrets from all services.     1. Backs up, Restore .env from backup and remove lock., Pull secrets from Vaultwarden and write .env (placeholder — requires bw CLI auth (+2 more)

### Community 58 - "Notion Connector"
Cohesion: 0.33
Nodes (3): NotionConnector, Create a page in a Notion database., Query a Notion database.

### Community 59 - "Model Routing Config"
Cohesion: 0.22
Nodes (8): cost_tracking, enabled, table, description, lastUpdated, routing_rules, $schema, version

### Community 60 - "Security Watchdog"
Cohesion: 0.42
Nodes (8): check_docker_socket_access(), check_fail2ban_bans(), check_secret_leaks_in_logs(), log(), main(), Post violation alert to Slack with approval buttons. Returns message ts., run_checks(), slack_alert()

### Community 61 - "Evaluator Retry Logic"
Cohesion: 0.33
Nodes (5): evaluate_with_retries(), notify_rejection(), Notify CEO on Slack that a task was rejected after max retries., Evaluate output and retry if it fails.      Args:         task: The original tas, Good output should pass immediately without retries.

### Community 62 - "Context Build Tests"
Cohesion: 0.25
Nodes (5): Tests for AI.darius.context, Should not compress when below turn threshold., Should compress when unsummarized turns reach threshold., build_context should assemble summaries + recent turns., TestContext

### Community 63 - "Kubernetes Ingress & Certs"
Cohesion: 0.25
Nodes (8): Let's Encrypt Production ClusterIssuer, Let's Encrypt Staging ClusterIssuer, K8s AWS Migration Guide, K8s Bootstrap (nginx-ingress + cert-manager), Client Site Template, Melanin Website Ingress, Melanin Website K8s Manifests, Client Network Policy Template

### Community 64 - "HUD Backend Dependencies"
Cohesion: 0.25
Nodes (8): docker SDK (HUD), fastapi (HUD), httpx (HUD), kubernetes (HUD), psycopg2-binary (HUD), python-jose (HUD), HUD Backend requirements.txt, uvicorn (HUD)

### Community 65 - "LLM Observability Dashboard"
Cohesion: 0.25
Nodes (8): _get_error_budgets(), _get_local_vs_cloud(), _get_per_agent_sli(), llm_observability(), Full LLM observability dashboard data., Per-agent SLI breakdown., Latest error budget status per SLO., Compare local (Ollama) vs cloud (Claude) model performance from Darius traces.

### Community 66 - "Google OAuth Flow"
Cohesion: 0.32
Nodes (5): google_auth(), main(), OAuthCallbackHandler, BaseHTTPRequestHandler, Run Google OAuth flow.

### Community 67 - "Google Calendar Connector"
Cohesion: 0.25
Nodes (3): GoogleCalendarConnector, List upcoming events., Create a calendar event.

### Community 68 - "Anthropic Model Config"
Cohesion: 0.25
Nodes (8): auth_env, base_url, models, type, haiku, opus, sonnet, anthropic

### Community 69 - "Darius v2 Tests"
Cohesion: 0.29
Nodes (5): Tests for Darius v2.0 — planning, evaluation, DAG execution, compressed context., # TODO: implement this, Tests for AI.darius.memory trace functions (unit-level, no DB)., log_trace should accept all expected parameters without error., TestMemory

### Community 70 - "Docs Graph Parser"
Cohesion: 0.33
Nodes (7): _get_doc_nodes(), _parse_glossary_concepts(), _parse_markdown_sections(), Path, Parse a markdown file into sections at h2 (##) level., Extract concept nodes from the Glossary (each bolded term in a table row)., Parse all MelaninDocs into nodes and infer edges.

### Community 71 - "Ollama Provider Config"
Cohesion: 0.29
Nodes (7): classify, embed, base_url, models, type, providers, ollama

### Community 72 - "UX/UI Design Agent"
Cohesion: 0.40
Nodes (4): Melanin Technologies — Design System & Specification Loaded statically into agen, _audit_screenshot(), handle(), Take a visual audit of the live site and return a summary.

### Community 73 - "SRE Agent"
Cohesion: 0.40
Nodes (5): _gather_live_status(), handle(), SRE Agent — Site Reliability Engineering for Melanin Technologies infrastructure, SRE agent: status reports use live data only (no LLM waste), diagnosis tasks use, Query ALL infrastructure (not project-scoped) and return formatted status lines.

### Community 74 - "Integration Tests"
Cohesion: 0.33
Nodes (4): Integration tests — verifies the full flow wiring., Simple task should plan (single step) → execute via smolagents → save., Multi-step plan should route through DAG executor., TestIntegration

### Community 75 - "Compliance & Security Docs"
Cohesion: 0.33
Nodes (6): Production Hosting Setup, BAA Policy, Compliance Checklist, Data Protection Policy, Disaster Recovery Test Procedure, Network Policy

### Community 76 - "Client Auth & TOTP"
Cohesion: 0.20
Nodes (6): HTTPAuthorizationCredentials, clients(), _generate_totp(), OrthoFlow client accounts — metadata + usage metrics., Generate current TOTP code., verify_token()

### Community 77 - "Integration Tool Wrapper"
Cohesion: 0.40
Nodes (3): IntegrationTool, Tool, Load OAuth credentials. Priority: env var → file → None.

### Community 78 - "Local Model Config"
Cohesion: 0.33
Nodes (6): base_url, models, status, type, darius-v1, darius-local

### Community 79 - "Credit Budget Guard"
Cohesion: 0.40
Nodes (5): CreditExhaustedError, _guard_credit_balance(), Pre-flight credit check. Raises if monthly spend is at 95%+ of budget.     This, Raised when monthly credit budget is nearly exhausted., Exception

### Community 80 - "DBA Agent"
Cohesion: 0.50
Nodes (4): _gather_db_health(), handle(), DBA Agent — Database Administration and Health for Melanin Technologies.  Respon, Query both databases for live health metrics.

### Community 81 - "Local Model Training Plan"
Cohesion: 0.40
Nodes (5): description, strategy, training_data, future, darius_local

### Community 82 - "LLM Default Parameters"
Cohesion: 0.40
Nodes (5): defaults, fallback, max_tokens, model, temperature

### Community 84 - "Infrastructure Status Query"
Cohesion: 0.50
Nodes (4): _docker_infrastructure(), infrastructure(), _k8s_infrastructure(), Query Kubernetes API for pod/service status.

### Community 85 - "WebSocket Live Data"
Cohesion: 0.50
Nodes (4): _get_live_data(), Get current system state for WebSocket push., websocket_endpoint(), WebSocket

### Community 86 - "Workflow Listing"
Cohesion: 0.50
Nodes (4): List all workflows (file-tree + legacy) with recent run data., workflows(), list_workflows(), List all available workflows (file-tree + legacy YAML templates).

### Community 88 - "HUD Monitoring Watchdog"
Cohesion: 0.50
Nodes (4): _alert_and_fix(), check_monitoring_gaps(), Verify HUD is recording health snapshots. Auto-fix if not., Alert Slack and restart the HUD container to restore monitoring.

### Community 89 - "Kubernetes Infrastructure"
Cohesion: 0.67
Nodes (3): K8s Infrastructure (Postgres + Ollama), K8s MCP Sidecars, K8s PVCs

### Community 114 - "Output Completeness Check"
Cohesion: 0.50
Nodes (3): _check_completeness(), Check for TODO/placeholder patterns., Outputs with TODO/placeholder patterns should fail completeness.

## Knowledge Gaps
- **187 isolated node(s):** `check-cert-expiry.sh script`, `type`, `onboard-client.sh script`, `npm-security-audit.sh script`, `scan-containers.sh script` (+182 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_check_endpoint_health()` connect `SRE Background Monitors` to `Backend Data & Charts`, `Credit Budget Guard`?**
  _High betweenness centrality (0.121) - this node is a cross-community bridge._
- **Why does `chat()` connect `FastAPI Task Server` to `Darius Agent Core`, `Credit Budget Guard`?**
  _High betweenness centrality (0.091) - this node is a cross-community bridge._
- **Why does `GmailConnector` connect `Gmail Connector` to `MCP Gateway Tools`, `Integration Base Connector`, `Backend Data & Charts`, `Integration Tool Wrapper`, `SRE Background Monitors`, `Integration Connectors Registry`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `SharedMemory` (e.g. with `SwarmAgent` and `DeltaExecutor`) actually correct?**
  _`SharedMemory` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `AgentSwarm` (e.g. with `SwarmAgent` and `SharedMemory`) actually correct?**
  _`AgentSwarm` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `check-cert-expiry.sh script`, `type`, `onboard-client.sh script` to the rest of the system?**
  _187 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Agent Contracts & Guardrails` be split into smaller, more focused modules?**
  _Cohesion score 0.05429864253393665 - nodes in this community are weakly interconnected._