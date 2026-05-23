"""
Playwright MCP — visual regression & screenshot service for the UXUIAgent.

Endpoints:
  POST /screenshot        { url, path?, full_page? }  → saves PNG, returns base64
  POST /screenshot/mobile { url }                     → mobile viewport screenshot
  POST /diff              { baseline, current }        → pixel diff score + base64 diff image
  POST /audit             { url }                      → screenshot all breakpoints at once
"""
import base64
import io
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from playwright.sync_api import sync_playwright
from PIL import Image, ImageChops, ImageEnhance

SCREENSHOTS_DIR = Path(os.environ.get("SCREENSHOTS_DIR", "/screenshots"))
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI()


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


@app.post("/screenshot")
def screenshot(body: dict):
    url = body.get("url")
    if not url:
        raise HTTPException(400, "url required")
    name = body.get("path", "screenshot.png")
    full_page = body.get("full_page", True)
    out = _screenshot(url, name, {"width": 1440, "height": 900}, full_page)
    return {"path": str(out), "image": _b64(out)}


@app.post("/screenshot/mobile")
def screenshot_mobile(body: dict):
    url = body.get("url")
    if not url:
        raise HTTPException(400, "url required")
    out = _screenshot(url, "screenshot-mobile.png", {"width": 390, "height": 844})
    return {"path": str(out), "image": _b64(out)}


@app.post("/diff")
def diff(body: dict):
    baseline_path = body.get("baseline")
    current_path = body.get("current")
    if not baseline_path or not current_path:
        raise HTTPException(400, "baseline and current paths required")

    b = Image.open(baseline_path).convert("RGB")
    c = Image.open(current_path).convert("RGB")

    # resize current to match baseline if dimensions differ
    if b.size != c.size:
        c = c.resize(b.size, Image.LANCZOS)

    diff_img = ImageChops.difference(b, c)
    # amplify diff for visibility
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


@app.post("/extract")
def extract(body: dict):
    """Extract fonts and CSS from a JS-rendered page by intercepting network requests."""
    url = body.get("url")
    if not url:
        raise HTTPException(400, "url required")

    fonts = []
    css_snippets = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        def handle_response(response):
            u = response.url
            if "font" in u.lower() or u.endswith((".woff", ".woff2", ".ttf", ".otf")):
                fonts.append(u)
            if "fonts.googleapis.com" in u:
                fonts.append(u)

        page.on("response", handle_response)
        try:
            page.goto(url, wait_until="networkidle", timeout=45000)
        except Exception:
            pass

        # extract computed font families from headings
        font_data = page.evaluate("""() => {
            const els = document.querySelectorAll('h1,h2,h3,p,body')
            const result = []
            els.forEach(el => {
                const s = window.getComputedStyle(el)
                result.push({
                    tag: el.tagName,
                    fontFamily: s.fontFamily,
                    fontWeight: s.fontWeight,
                    fontSize: s.fontSize,
                })
            })
            return result
        }""")

        browser.close()

    return {"font_requests": fonts[:20], "computed_fonts": font_data[:10]}
    url = body.get("url")
    if not url:
        raise HTTPException(400, "url required")

    results = {}
    viewports = {
        "desktop": {"width": 1440, "height": 900},
        "tablet":  {"width": 768,  "height": 1024},
        "mobile":  {"width": 390,  "height": 844},
    }
    for name, vp in viewports.items():
        out = _screenshot(url, f"audit-{name}.png", vp)
        results[name] = {"path": str(out), "image": _b64(out)}

    return results


@app.post("/extract")
def extract(body: dict):
    """Intercept network requests to find fonts used by a JS-rendered page."""
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
            document.querySelectorAll('h1,h2,h3,p,body').forEach(el => {
                const s = window.getComputedStyle(el)
                result.push({ tag: el.tagName, fontFamily: s.fontFamily, fontWeight: s.fontWeight, fontSize: s.fontSize })
            })
            return result
        }""")

        browser.close()

    return {"font_requests": fonts[:30], "computed_fonts": font_data[:15]}
