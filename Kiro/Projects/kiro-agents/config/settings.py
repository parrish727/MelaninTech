import os
from dotenv import load_dotenv

load_dotenv()

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
SLACK_SIGNING_SECRET = os.environ["SLACK_SIGNING_SECRET"]
SLACK_CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
POSTGRES_DSN = os.environ["POSTGRES_DSN"]

AGENT_URLS = {
    "code":     "http://code-agent:8000",
    "file":     "http://file-agent:8000",
    "scaffold": "http://scaffold-agent:8000",
    "backend":  "http://backend-agent:8000",
    "frontend": "http://frontend-agent:8000",
    "deploy":   "http://deploy-agent:8000",
    "devops":   "http://deploy-agent:8000",  # alias — CI failure routing
    "support":  "http://support-agent:8000",
    "sre":      "http://sre-agent:8000",
    "dba":      "http://dba-agent:8000",
    "qa":       "http://qa-agent:8000",
    "darius":   "http://darius-agent:8000",
}

PROJECTS_BASE = "/app/Projects"
MCP_URL = os.environ.get("MCP_URL", "http://mcp-server:9000")
