"""
SEO Intelligence Pipeline — Architecture & Data Model

Melanin Technologies Inc.
Target: melanin-tech.com (initial), then templated for client sites

Pipeline Overview:
  ┌─────────────────────────────────────────────────────────────┐
  │                    Weekly Cron Trigger                        │
  │                  (Sunday night, automated)                   │
  └─────────────────────┬───────────────────────────────────────┘
                        │
  ┌─────────────────────▼───────────────────────────────────────┐
  │  1. DATA COLLECTION (parallel)                               │
  │     ├── GSC Connector → queries, impressions, CTR, position  │
  │     ├── SearXNG SERP Tracker → live ranking positions        │
  │     └── Keyword Discovery → related terms, competitors       │
  └─────────────────────┬───────────────────────────────────────┘
                        │
  ┌─────────────────────▼───────────────────────────────────────┐
  │  2. ANALYSIS (Darius SEO Agent)                              │
  │     ├── Declining pages (position/CTR dropped)               │
  │     ├── Near-page-1 keywords (positions 11-20)               │
  │     ├── FAQ gaps (queries with no matching content)           │
  │     ├── Internal link opportunities                          │
  │     ├── CTA effectiveness (low CTR on key pages)             │
  │     └── Content freshness (pages not updated in 60+ days)    │
  └─────────────────────┬───────────────────────────────────────┘
                        │
  ┌─────────────────────▼───────────────────────────────────────┐
  │  3. TICKET GENERATION                                        │
  │     ├── Create /task-internal tickets for each opportunity   │
  │     ├── Priority scoring (impact × effort)                   │
  │     └── Slack summary posted for CEO review                  │
  └─────────────────────────────────────────────────────────────┘

Data Sources:
  - Google Search Console API (requires webmasters.readonly scope)
  - SearXNG (self-hosted, already running as a container)
  - Postgres (storage for all SEO data)

No paid third-party APIs. Everything self-hosted.
"""
