"""
One-off script to post system update summary to Slack.
Run: python post_updates.py
"""
import os
from dotenv import load_dotenv
from slack_sdk import WebClient

load_dotenv()
client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])

message = """
*📋 Melanin Technologies Inc. — System Updates*

Three documents have been created/updated:

*1. Company Manifesto* — Vision, mission, services, and values for Melanin Technologies Inc.
*2. Internal Onboarding & CEO Knowledge Base* — Company structure, legal docs, internal systems, operational runbook, and growth roadmap.
*3. Kiro System Manifesto* — Updated to reflect all recent changes:
  • 5 new delivery agents: ScaffoldAgent, BackendAgent, FrontendAgent, DeployAgent, SupportAgent
  • Human-in-the-loop modify flow (edit proposals before approving)
  • Vector memory via pgvector + Ollama (nomic-embed-text, fully local)
  • Support contract enforcement — 90-day post-launch + usage-based ticket plans
  • n8n added for internal workflow automation
  • Granular Docker volume controls per agent
  • Auto-sync hook — docs update automatically when system files change

Stack: Next.js + TypeScript · FastAPI · PostgreSQL · Docker · Rust · n8n
"""

client.chat_postMessage(channel="#all_melanin_technologies_inc", text=message)
print("✅ Posted to #all_melanin_technologies_inc")

ticket_update = """
*🎫 Internal Ticket Tracking System — Now Live*

All tasks submitted via `/task` are now automatically tracked as tickets in our Postgres database.

*How it works:*
• Every `/task` submission opens a ticket with status `open`
• Approving a proposal → ticket moves to `done`
• Rejecting a proposal → ticket moves to `rejected`

*Querying tickets via Slack:*
```
/tickets                     — all recent tickets
/tickets client-a            — all tickets for a specific client
/tickets client-a open       — filter by client + status
```

*Statuses:* `open` · `done` · `rejected`

All ticket history is stored in Postgres and persists across restarts.
"""

client.chat_postMessage(channel="#melanated_agent_testing", text=ticket_update)
print("✅ Posted to #melanated_agent_testing")
