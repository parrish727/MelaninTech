import os
import uvicorn
from agents.base_agent import create_app

PROJECTS_BASE = os.environ.get("PROJECTS_BASE", "/app/Projects")

# Project registry — each client is isolated, never cross-referenced
PROJECT_PATHS = {
    "melanin-tech-website": os.environ.get("MELANIN_WEBSITE_PATH", "/app/melanin-tech-website"),
    "orthoflow-ai": "/app/orthoflow-frontend",
}

# Project-specific context — ONLY loaded for the matching project
PROJECT_CONTEXT = {
    "melanin-tech-website": """
Project: Melanin Technologies Website (Next.js)
- Components: components/ (Nav, Hero, Services, HowWeWork, WhoWeAre, Stack, Contact, Footer)
- Pages: app/ (page.tsx, layout.tsx, globals.css)
- Colors: #3D5A99, #2C4275, #1E2E52, #B5A84B, #D4C96A, #6B9E78, #F5F3EE
- Fonts: Syne (headings), Inter (body)
""",
    "orthoflow-ai": """
Project: OrthoFlow AI (React + Vite + Tailwind v4)
Path: /app/orthoflow-frontend
Framework: React 19, Vite, Tailwind CSS v4 (@tailwindcss/vite plugin)
Pages: src/pages/ (Login.tsx, Dashboard.tsx, InvoiceDetail.tsx, Invoices.tsx, Analytics.tsx, Settings.tsx, Account.tsx, Privacy.tsx, Terms.tsx)
Components: src/components/ (Tooltip.tsx)
API client: src/lib/api.ts
Routing: src/main.tsx (react-router-dom)
Styling: Tailwind utility classes, Apple-style design (rounded-2xl, bg-[#f5f5f7], shadow-sm)
Icons: lucide-react
This is a client-facing SaaS app for orthodontic practices. Keep it clean, professional, intuitive.
Do NOT ask for clarification — you have all the context needed. Just write the code.
""",
}

SYSTEM_PROMPT = None  # Loaded from agents/skills/frontend.skill.md at runtime



def handle(task: str, project: str, proposal_text: str, model: str) -> dict:
    # Resolve project path — strict isolation
    project_path = PROJECT_PATHS.get(project.lower())
    if not project_path:
        project_path = os.path.join(PROJECTS_BASE, project, "frontend")

    # Load appropriate context — SEO tasks get SEO skill
    task_lower = task.lower()
    if any(k in task_lower for k in ["seo", "aeo", "schema", "json-ld", "sitemap", "faq", "indexnow"]):
        from agents.base_agent import load_skill
        seo_context = load_skill("seo")
        context = PROJECT_CONTEXT.get(project.lower(), "") + "\n\n" + seo_context
    else:
        context = PROJECT_CONTEXT.get(project.lower(), "")

    return {
        "agent": "FrontendAgent",
        "model": model,
        "description": f"FrontendAgent [{project}]: {task[:80]}",
        "action": "frontend",
        "args": {
            "task": task,
            "project": project,
            "project_path": project_path,
            "proposal": f"PROJECT: {project}\n{context}\n\n{proposal_text}",
        },
    }


app = create_app("FrontendAgent", SYSTEM_PROMPT, handle)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
