# Session Context: August 3–13, 2026

## Major Accomplishments

### 1. Qdrant Semantic Layer (Aug 3-4)
- Qdrant v1.14.0 deployed on agent-net (PR #1)
- integrations/qdrant_client.py: SemanticLayer class (embed, upsert, search, filter, batch)
- Migrated 1,663 vectors from pgvector + graphify → 6 Qdrant collections
- Dual-write: orchestrator/memory.py + AI/darius/memory.py write to both Qdrant AND pgvector
- Read path: Qdrant primary, pgvector fallback
- Fixed: Qdrant healthcheck (wget not available, switched to bash /dev/tcp)
- Collections: task_memory(60), conversation_memory(134), graph_nodes(1465), context_summaries(4), business_context(564), eval_baselines(10)

### 2. Observability Stack (Aug 4-5, PR #2)
- Grafana Tempo v2.6.1 + OTEL Collector v0.108.0 (distributed tracing)
- integrations/tracing.py: @traced decorator, span(), get_trace_id()
- Orchestrator + Darius instrumented with trace propagation
- Fixed: Tempo healthcheck (wget for alpine), OTEL Collector healthcheck disabled (distroless)

### 3. Drift Detection + QA Eval Gate (Aug 4-5, PR #2)
- integrations/drift_detector.py: compares outputs to baselines, alerts on drift > 0.15
- scripts/eval_runner.py: golden-set evaluator with --lob support, per-LOB scoring
- eval/golden_sets/ restructured into per-LOB folders (core, orthoflow, parcelpro, artistos, htc, melanin-core)
- 21 test cases total
- Daily cron installed (6am): scripts/daily_drift_check.sh
- Eval baseline: 77.8% overall (OrthoFlow 100%, HTC 100%, ParcelPro 89%)

### 4. Document Extraction Pipeline (Aug 4-5, PR #2)
- integrations/doc_extractor.py: MD/HTML/PDF/DOCX → chunks → Qdrant business_context
- config/lob_manifest.yaml: standardized LOB onboarding registry (5 LOBs)
- 564 vectors ingested (119 files across 5 LOBs)
- PyMuPDF + python-docx installed for PDF/DOCX support
- Darius context.py wired to query business_context with LOB-scoped retrieval

### 5. LOB-Scoped Evaluation (Aug 6, PR #3)
- context.py: _recall_business_context() with project→LOB name mapping
- eval_runner.py rewritten with --lob flag, per-LOB score reporting
- drift_detector.py updated for per-LOB folder structure + LOB metadata in baselines

### 6. Comprehensive Documentation (Aug 6)
- MelaninDocs local git initialized (no remote, stays on machine)
- 13 new docs created:
  - Architecture/: SystemArchitecture, DariusAgent, HUD, ObservabilityStack
  - Processes/: DeploymentProcess, LOBOnboarding, QualityGate, AI_SRE_Workstation_Prompt
  - LOBs/: OrthoFlow, ParcelPro, ArtistOS, HTC
  - TeamStructure.md
- Manifesto updated (tech stack, AI platform, Active Projects, infra)
- All docs ingested into business_context (480→564 points)

### 7. Evaluator v2 + Autonomous File Writes (Aug 6, PR #4)
- AI/darius/task_classifier.py: CODE/QUESTION/DEPLOY/ANALYSIS classification
- AI/darius/evaluation_prompts.py: per-type scoring (4 prompts, different thresholds)
- evaluator.py: skips structural checks for non-CODE tasks, uses type-appropriate prompt
- autonomous.py: _extract_and_write_files() — parses code blocks, writes to disk
- Security: only writes within PROJECTS_BASE, blocks .env/credentials/keys
- Ticket #79 resolved

### 8. Multi-Burn-Rate Error Budgeting (Aug 7, PR #5)
- integrations/error_budget.py (550 lines): ErrorBudgetEngine class
- Fast burn: 14.4x over 1h → critical page (exhausts in ~2 days)
- Slow burn: 6x over 6h → warning ticket (exhausts in ~5 days)
- Feature freeze: auto-blocks deploys when budget < 20% (Redis flag)
- Replaced noisy threshold-based alerts in HUD watchdog
- config/slo_definitions.yaml: formalized SLO/SLI definitions
- deploy_pipeline.py: feature freeze gate added
- HUD backend restarted with volume-mounted main.py (fixed stale baked code)

### 9. Enterprise AI SRE Multi-Agent Prompt (Aug 11, Ticket #82)
- MelaninDocs/Processes/Enterprise_AI_SRE_MultiAgent_Prompt.md (336 lines)
- Banking-grade + multi-agent delegation via Claude Code/CLI
- 7 skill profiles, knowledge cabinet, templates/scripts library
- Maps: Dynatrace=HUD, Claude Code=Orchestrator, GitLab=Repository
- Vaultwarden reference removed (kept generic)

## Open Items / TODO (Revisit After Infra Migration)

### Vaultwarden .env Sync
- 4 secrets in .env not formally in secrets policy:
  - N8N_PASSWORD
  - PLAID_SECRET (duplicate line in .env — remove one)
  - POSTGRES_DSN (full connection string)
  - VAULTWARDEN_SMTP_PASSWORD
- Action: verify these are in Vaultwarden vault, remove .env duplicate, update secrets policy

### Open Tickets
- #41: Email OrthoFlow arch doc (blocked by SendGrid #72)
- #71: EPIC — Local model migration + GPU hardware (waiting on hardware)
- #72: Configure Twilio SendGrid (backlog)

### Infrastructure State (as of Aug 13)
- 75+ containers running
- Qdrant: 6 collections, ~2,237+ vectors
- Tempo + OTEL: healthy, traces collecting
- Daily drift cron: 6am
- Feature freeze: inactive (budgets healthy)
- HUD backend: volume-mounted main.py (no rebuild needed for code changes now)

## PRs Merged (This Session)
- #1: Qdrant semantic layer
- #2: Observability + eval + extraction
- #3: LOB-scoped eval/context
- #4: Evaluator v2 + autonomous file writes
- #5: Multi-burn-rate error budgeting

## Key Technical Decisions
- MelaninDocs stays LOCAL (in .gitignore, never pushed to GitHub)
- MelaninDocs has its own local git (no remote)
- Qdrant is PRIMARY for vector search, pgvector is fallback
- Darius uses Claude exclusively for inference (Ollama for embeddings only)
- Autonomous mode writes files via _extract_and_write_files() post-processor
- Error budget alerts: multi-window confirmation (no more single-threshold noise)
- Evaluator classifies task type BEFORE scoring (non-code tasks don't need code blocks)
- HUD backend main.py is now volume-mounted (no container rebuild needed for code updates)
