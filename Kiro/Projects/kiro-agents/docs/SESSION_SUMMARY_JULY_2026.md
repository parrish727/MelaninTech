# Melanin Technologies — Architecture Work Summary (July 5-19, 2026)

## What Was Built

### Phase 1: Darius v2.0
- Planner (DAG decomposition, Sonnet), Evaluator (3-retry + Slack reject, Sonnet), Executor (parallel), Context (auto-compress), Model Router
- 21-test suite passing

### Phase 2: SEO Intelligence Pipeline
- GSC connector, SearXNG keyword discovery, SERP tracking, 5-pass analysis, auto-tickets, Slack summary
- Weekly cron (Sundays 11pm), both sites: melanin-tech.com (id=1) + orthoflowsolutions.com (id=4)
- GSC verified for both domains

### Phase 3: Visual-Aware Frontend
- Playwright MCP v2.0 (screenshots, Lighthouse, diff, extraction)
- Design system manifest (design-system.json)
- Self-improvement loop (SEO → frontend agent → preview → validate → approve)

### Phase A: Unified Tool Registry + MCP Gateway
- _registry.json (65 tools cataloged)
- mcp_gateway.py: Slack, Google, Cloudflare, Docker tools (port 9014)
- GatewayTool added to Darius

### Phase B: File-Tree Workflow Engine
- workflow_engine.py: list, load, create, modify, migrate workflows
- seo-improve first file-tree workflow (5 steps)
- Darius can create/modify workflows at runtime

### Phase C: Model Router
- _models.json: 8 rules, 3 providers (Anthropic, Ollama, future Darius local)
- Planning + Eval upgraded Haiku → Sonnet

### Phase D: Scoped RAG
- scoped_rag.py: per-project/workflow vector namespaces
- Table: scoped_memory (namespace, content, metadata, embedding)

### Phase E: HUD Integration
- /api/workflows endpoint added, frontend tab deferred

### Training Data Pipeline
- export_training_data.py: JSONL + conversation format for fine-tuning

### OrthoFlow Marketing Website
- orthoflow-marketing/ deployed at orthoflowsolutions.com (port 3010)
- Competitive positioning: comparison table vs Ortho2/Dentrix/Eaglesoft

### melanin-tech.com Updates
- Positioning: "We Build It, Run It, and Grow It With You"
- Contact form FIXED: POST /api/contact → Slack #melanin_client_interaction
- /insights blog page (3 stubs)

---

## PENDING: OrthoFlow Trademark Filing

**Status:** NOT YET FILED — do after infrastructure migration

- "OrthoFlow" not trademarked in USPTO (as of July 2026)
- Conflict check: orthoflow.org (UK orthopaedic surgery app — different specialty/geography)
- File TEAS Plus: $250/class, Classes 009 + 042
- Owner: Melanin Technologies Inc. (NC corporation)
- Filing basis: 1(a) Use in Commerce, first use: 2026-05-08
- Specimens: Screenshots of app.orthoflowsolutions.com + marketing site

**Class 009:** Downloadable computer software for orthodontic practice management — patient records, scheduling, clinical charting, imaging, invoice processing, insurance claims, payments, communications, treatment planning, appliance/archwire tracking, AI billing classification, reporting, team management.

**Class 042:** SaaS for orthodontic practice management — same features as above plus patient portal, integration with third-party accounting software.

**Also file:** "OrthoFlow Solutions" separately.

**Speed:** Self-file tonight ($500 for 2 classes) for priority date. Get IP attorney to handle office actions later.

---

## Backlog
- HUD Workflows tab frontend (main.tsx 77KB)
- Blog MDX/content system for /insights
- Darius local model training (needs 4-8 weeks of traces)
- Infrastructure migration (upcoming)
