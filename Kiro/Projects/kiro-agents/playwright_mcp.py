"""
Playwright + Lighthouse MCP — visual awareness & quality scoring for agents.

Endpoints:
  POST /screenshot         { url, path?, full_page? }  → saves PNG, returns base64
  POST /screenshot/mobile  { url }                     → mobile viewport screenshot
  POST /diff               { baseline, current }       → pixel diff score + diff image
  POST /audit/visual       { url }                     → screenshot all breakpoints
  POST /audit/lighthouse   { url, categories? }        → Lighthouse performance scores
  POST /extract            { url }                     → extract fonts/CSS from rendered page
  GET  /health                                         → health check
"""
import base64
import io
import json
import os
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from playwright.sync_api import sync_playwright
from PIL import Image, ImageChops, ImageEnhance

SCREENSHOTS_DIR = Path(os.environ.get("SCREENSHOTS_DIR", "/screenshots"))
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Playwright + Lighthouse MCP", version="2.0.0")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def _screenshot(url: str, name: str, viewport: dict, full_page: bool = True) -> Path:
    out = SCREENSHOTS_DIR / name
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=viewport)
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.screenshot(path=str(out), full_page=full_page)
        browser.close()
    return out


# ── Screenshot Endpoints ──────────────────────────────────────────────────────

@app.post("/screenshot")
def screenshot(body: dict):
    """Take a desktop screenshot of a URL."""
    url = body.get("url")
    if not url:
        raise HTTPException(400, "url required")
    name = body.get("path", "screenshot.png")
    full_page = body.get("full_page", True)
    out = _screenshot(url, name, {"width": 1440, "height": 900}, full_page)
    return {"path": str(out), "image": _b64(out)}


@app.post("/screenshot/mobile")
def screenshot_mobile(body: dict):
    """Take a mobile screenshot (iPhone 14 viewport)."""
    url = body.get("url")
    if not url:
        raise HTTPException(400, "url required")
    out = _screenshot(url, "screenshot-mobile.png", {"width": 390, "height": 844})
    return {"path": str(out), "image": _b64(out)}


# ── Visual Diff ───────────────────────────────────────────────────────────────

@app.post("/diff")
def diff(body: dict):
    """Compare two screenshots and return pixel diff score."""
    baseline_path = body.get("baseline")
    current_path = body.get("current")
    if not baseline_path or not current_path:
        raise HTTPException(400, "baseline and current paths required")

    b = Image.open(baseline_path).convert("RGB")
    c = Image.open(current_path).convert("RGB")

    if b.size != c.size:
        c = c.resize(b.size, Image.LANCZOS)

    diff_img = ImageChops.difference(b, c)
    diff_img = ImageEnhance.Brightness(diff_img).enhance(5.0)

    pixels = list(diff_img.getdata())
    changed = sum(1 for px in pixels if any(v > 10 for v in px))
    score = round(changed / len(pixels) * 100, 2)

    out = SCREENSHOTS_DIR / "diff.png"
    diff_img.save(str(out))

    return {
        "diff_score_pct": score,
        "changed_pixels": changed,
        "total_pixels": len(pixels),
        "diff_image": _b64(out),
    }


# ── Visual Audit (multi-breakpoint) ──────────────────────────────────────────

@app.post("/audit/visual")
def audit_visual(body: dict):
    """Screenshot a URL at desktop, tablet, and mobile breakpoints."""
    url = body.get("url")
    if not url:
        raise HTTPException(400, "url required")

    viewports = {
        "desktop": {"width": 1440, "height": 900},
        "tablet": {"width": 768, "height": 1024},
        "mobile": {"width": 390, "height": 844},
    }

    results = {}
    for name, vp in viewports.items():
        out = _screenshot(url, f"audit-{name}.png", vp)
        results[name] = {"path": str(out), "image": _b64(out)}

    return results


# ── Lighthouse Audit ──────────────────────────────────────────────────────────

@app.post("/audit/lighthouse")
def audit_lighthouse(body: dict):
    """
    Run Lighthouse audit on a URL.

    Args:
        url: URL to audit
        categories: List of categories to audit (default: all)
            Options: performance, accessibility, best-practices, seo

    Returns:
        Scores for each category + key metrics.
    """
    url = body.get("url")
    if not url:
        raise HTTPException(400, "url required")

    categories = body.get("categories", ["performance", "accessibility", "best-practices", "seo"])

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "report.json")

        cmd = [
            "lighthouse", url,
            "--output=json",
            f"--output-path={output_path}",
            "--chrome-flags=--headless --no-sandbox --disable-gpu",
            "--quiet",
        ]
        for cat in categories:
            cmd.append(f"--only-categories={cat}")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120,
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(504, "Lighthouse audit timed out (120s)")

        if not os.path.exists(output_path):
            error_msg = result.stderr[:500] if result.stderr else "Unknown error"
            raise HTTPException(500, f"Lighthouse failed: {error_msg}")

        with open(output_path) as f:
            report = json.load(f)

    # Extract scores
    scores = {}
    for cat_id, cat_data in report.get("categories", {}).items():
        scores[cat_id] = {
            "score": round(cat_data.get("score", 0) * 100),
            "title": cat_data.get("title", cat_id),
        }

    # Extract key performance metrics
    metrics = {}
    audits = report.get("audits", {})
    metric_keys = [
        "first-contentful-paint",
        "largest-contentful-paint",
        "total-blocking-time",
        "cumulative-layout-shift",
        "speed-index",
        "interactive",
    ]
    for key in metric_keys:
        if key in audits:
            metrics[key] = {
                "value": audits[key].get("numericValue"),
                "display": audits[key].get("displayValue", ""),
                "score": round((audits[key].get("score", 0) or 0) * 100),
            }

    # Extract failed audits (opportunities for improvement)
    opportunities = []
    for audit_id, audit_data in audits.items():
        if audit_data.get("score") is not None and audit_data["score"] < 0.5:
            if audit_data.get("details", {}).get("type") == "opportunity":
                opportunities.append({
                    "id": audit_id,
                    "title": audit_data.get("title", ""),
                    "description": audit_data.get("description", "")[:200],
                    "score": round(audit_data["score"] * 100),
                })

    return {
        "url": url,
        "scores": scores,
        "metrics": metrics,
        "opportunities": opportunities[:10],
    }


# ── Font/CSS Extraction ───────────────────────────────────────────────────────

@app.post("/extract")
def extract(body: dict):
    """Extract fonts and computed styles from a JS-rendered page."""
    url = body.get("url")
    if not url:
        raise HTTPException(400, "url required")

    fonts = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        def handle_response(response):
            u = response.url
            if any(x in u.lower() for x in ["font", ".woff", ".ttf", ".otf", "fonts.google", "fonts.gstatic"]):
                fonts.append(u)

        page.on("response", handle_response)
        try:
            page.goto(url, wait_until="networkidle", timeout=45000)
        except Exception:
            pass

        font_data = page.evaluate("""() => {
            const result = []
            document.querySelectorAll('h1,h2,h3,h4,p,body,a,button,span').forEach(el => {
                const s = window.getComputedStyle(el)
                result.push({
                    tag: el.tagName,
                    text: el.textContent.trim().substring(0, 50),
                    fontFamily: s.fontFamily,
                    fontWeight: s.fontWeight,
                    fontSize: s.fontSize,
                    color: s.color,
                    lineHeight: s.lineHeight,
                })
            })
            return result
        }""")

        # Extract color palette from page
        colors = page.evaluate("""() => {
            const colors = new Set()
            document.querySelectorAll('*').forEach(el => {
                const s = window.getComputedStyle(el)
                if (s.backgroundColor && s.backgroundColor !== 'rgba(0, 0, 0, 0)') colors.add(s.backgroundColor)
                if (s.color) colors.add(s.color)
            })
            return [...colors].slice(0, 30)
        }""")

        browser.close()

    return {
        "font_requests": fonts[:30],
        "computed_fonts": font_data[:20],
        "color_palette": colors,
    }


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "playwright-lighthouse-mcp", "version": "2.0.0"}
