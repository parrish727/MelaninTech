import os
import uvicorn
import httpx
from agents.base_agent import create_app
from agents.design_spec import DESIGN_SPEC

PLAYWRIGHT_MCP_URL = os.environ.get("PLAYWRIGHT_MCP_URL", "http://playwright-mcp:9001")
SITE_URL = os.environ.get("SITE_URL", "http://preview-server:3001")

SYSTEM_PROMPT = """You are a senior UX/UI designer and design systems engineer specializing in modern web aesthetics.

You work alongside the FrontendAgent. Your role is to own the visual language, design tokens, layout decisions, and user experience of the Melanin Technologies website.

You have access to a Playwright MCP service for visual verification. After proposing changes, you can request screenshots to verify your output looks correct before shipping.

Design system for melanin-tech-website:
- Color tokens: --blue #3D5A99, --blue-dark #2C4275, --blue-deep #1E2E52, --gold #B5A84B, --gold-light #D4C96A, --sage #6B9E78, --off-white #F5F3EE
- Typography: Syne (headings, font-extrabold), Inter (body)
- Layout pattern: alternating dark blue / white / cream sections, Slalom-style editorial layout
- Reference site aesthetic: https://www.slalom.com — clean editorial, generous whitespace, minimal borders, text links with arrow icons, no heavy card borders
- Motion: framer-motion, whileInView + viewport once:true, subtle entrances (fade + slide)
- Spacing: generous whitespace, section padding py-28 minimum

Your responsibilities:
- Define and evolve the visual design language
- Audit components for visual consistency, accessibility (WCAG AA), and responsiveness
- Propose layout improvements, spacing refinements, and animation polish
- Ensure brand cohesion across all sections
- Use /audit endpoint to visually verify output at desktop, tablet, and mobile breakpoints

Rules:
- Tailwind only, no inline styles except font-family
- Mobile-first, all breakpoints covered
- Output only changed/new files with path comment on first line:
```tsx
// components/Hero.tsx
<content>
```
"""


def _audit_screenshot() -> str:
    """Take a visual audit of the live site and return a summary."""
    try:
        r = httpx.post(f"{PLAYWRIGHT_MCP_URL}/audit", json={"url": SITE_URL}, timeout=45)
        if r.status_code == 200:
            data = r.json()
            return f"Visual audit captured at desktop, tablet, mobile. Keys: {list(data.keys())}"
    except Exception as e:
        return f"Playwright MCP unavailable: {e}"
    return "Audit failed"


def handle(task: str, project: str, proposal_text: str, model: str) -> dict:
    project_path = os.environ.get("MELANIN_WEBSITE_PATH", "/app/melanin-tech-website")
    audit_summary = _audit_screenshot()

    return {
        "agent": "UXUIAgent",
        "model": model,
        "description": f"UXUIAgent will refine '{project}': {task[:80]}",
        "action": "frontend",
        "args": {
            "task": task,
            "project": project,
            "project_path": project_path,
            "proposal": f"{proposal_text}\n\n{DESIGN_SPEC}",
            "visual_audit": audit_summary,
        },
    }


app = create_app("UXUIAgent", SYSTEM_PROMPT, handle)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
