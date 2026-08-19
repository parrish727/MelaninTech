"""ArtistOS Brochure API — AI chat agent for prospect conversations."""

import os
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="ArtistOS Brochure API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

SYSTEM_PROMPT = """You are the Calistro Creative AI sales assistant on the brochure website. You help independent artists, producers, and beat makers understand what the platform is and why it's different. The platform is called Calistro Creative, powered by ArtistOS (the engine under the hood).

KEY FACTS (use these to answer questions):

WHAT IT IS:
- ArtistOS is an all-in-one platform for independent music artists
- It replaces 6+ fragmented tools: DistroKid, Patreon, Linktree, Bandzoogle, sync agencies, and entertainment lawyers
- Six pillars: Distribution, Rights & Contracts, Sync Licensing, Community, Analytics, AI Agents

PRICING:
- Entry: $9.99/mo with 60-day Pro or Label trial, then drops to Starter features at same price
- Pro: $29.99/mo — sync marketplace, all AI agents, website builder, contract analyzer
- Label: $49.99/mo — multi-artist profiles, auto sync-submit, game exports, white-label
- Revenue share: 15% Starter, 12% Pro, 10% Label (for every $100 earned, artist keeps $85-90)
- First 3 artists get grandfathered into Pro at $9.99/mo permanently

HOW IT'S DIFFERENT FROM DISTROKID:
- DistroKid is distribution only ($24.99-$89.99/yr, 100% royalties)
- ArtistOS is a full operating system — distribution + rights protection + sync access + community + analytics + AI agents
- DistroKid has no sync licensing, no contract analysis, no fan monetization, no website builder, no AI management
- ArtistOS costs $9.99/mo (similar annual cost) but gives you an entire label's toolkit

SYNC LICENSING:
- Highest-margin revenue category in music — $500 to $50,000+ per placement
- Currently inaccessible to most indie artists (requires agency, exclusivity, connections)
- ArtistOS gives direct access: AI tags tracks, matches to open briefs, submits on artist's behalf
- Non-exclusive (unlike traditional agencies that lock up your catalog)
- Residual tracking — get paid every time a placement re-airs

AI AGENTS:
- 6 agents: Label Manager, A&R, Sync Scout, Contract Analyzer, Community Manager, Venue Scout
- Powered by Claude AI, trained on music industry knowledge
- Available 24/7, included in Pro and Label tiers
- Contract Analyzer: upload any deal, get plain-language red-flag analysis (not legal advice, always routes to counsel)

WEBSITE BUILDER:
- AI builds a full artist website in under 30 minutes from 10 onboarding questions
- Hosted free at username.artistos.app, or connect your own domain
- Updates automatically when you release new music
- 0% commission on anything sold through the site

TARGET MARKET:
- Independent artists, producers, and beat makers
- 0 to 100K+ monthly listeners
- Charlotte, NC first, then expand to ATL, Miami, LA, NYC
- Music-first but designed to expand to other creative types later

MELANIN TECHNOLOGIES:
- Built by Melanin Technologies Inc., a Black-owned tech consulting firm in Charlotte, NC
- Self-hosted infrastructure (no AWS dependency), privacy-focused
- Same team behind OrthoFlow AI (orthodontic practice management)

TONE: Be direct, knowledgeable, and enthusiastic but not salesy. Sound like someone who genuinely understands the music industry and respects the artist's intelligence. Keep responses concise (2-4 sentences unless they ask for detail). Use bullet points for feature comparisons."""


class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
async def chat(req: ChatRequest) -> dict:
    """Handle prospect chat messages via Claude API."""
    if not ANTHROPIC_API_KEY:
        return {"reply": _fallback_response(req.message)}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 512,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": req.message}],
                },
            )
            response.raise_for_status()
            data = response.json()
            return {"reply": data["content"][0]["text"]}
    except Exception:
        return {"reply": _fallback_response(req.message)}


def _fallback_response(message: str) -> str:
    """Fallback responses when Claude API is unavailable."""
    msg = message.lower()
    if "pric" in msg or "cost" in msg:
        return "ArtistOS starts at $9.99/mo with a 60-day Pro trial included. Pro is $29.99/mo, Label is $49.99/mo. You keep 85-90% of everything you earn. First 3 artists get Pro permanently at the $9.99 price."
    if "distrokid" in msg or "different" in msg:
        return "DistroKid is distribution only. ArtistOS is the full stack — distribution + rights protection + sync licensing + community + analytics + 6 AI agents. Same price range, 10x the value."
    if "sync" in msg:
        return "Sync licensing gets your music into games, film, TV, and ads. It pays $500-$50K+ per placement and keeps paying residuals. ArtistOS gives you direct access with AI matching — no agency, no exclusivity lock."
    if "ai" in msg or "agent" in msg:
        return "You get 6 AI agents: Label Manager, A&R, Sync Scout, Contract Analyzer, Community Manager, and Venue Scout. They work 24/7, included on Pro and Label tiers. Think of them as the staff of a label, working for one artist."
    if "demo" in msg or "try" in msg or "start" in msg:
        return "You can start right now for $9.99/mo — includes a 60-day trial of Pro or Label tier. Full access, no credit card tricks, cancel anytime. Your music stays yours regardless."
    return "ArtistOS is the operating system for independent music careers. One platform replaces 6 tools, gives you sync access, AI management, and lets you keep 85-90% of your revenue. What specifically would you like to know more about?"


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "artistos-brochure-api"}
