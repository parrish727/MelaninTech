#!/usr/bin/env python3
"""
Register both sites in the SEO pipeline.
Run inside Docker network (has access to Postgres):

  docker run --rm --network docker_agent-net \
    -v $(pwd)/integrations:/app/integrations:ro \
    -v $(pwd)/scripts:/app/scripts:ro \
    -e POSTGRES_DSN="postgresql://kiro:kiro_secret@postgres:5432/kiro" \
    -e SEARXNG_URL="http://searxng:8080" \
    python:3.11-slim \
    bash -c "pip install -q psycopg2-binary httpx && python3 /app/scripts/register_seo_sites.py"
"""
import sys
sys.path.insert(0, "/app")

from integrations.seo.models import register_site, upsert_keyword


def main():
    # ── melanin-tech.com (already registered, ensure keywords) ────────────────
    site = register_site("melanin-tech.com", "sc-domain:melanin-tech.com")
    print(f"✅ melanin-tech.com registered (id={site['id']})")

    melanin_seeds = [
        ("custom software development charlotte", "commercial"),
        ("ai software company", "commercial"),
        ("technology consulting charlotte nc", "commercial"),
        ("self-hosted infrastructure provider", "commercial"),
        ("software in a service", "informational"),
        ("saas development company", "commercial"),
        ("ai consulting", "commercial"),
        ("hire software developer charlotte", "commercial"),
        ("custom ai solutions", "commercial"),
        ("melanin technologies", "brand"),
        ("docker hosting provider", "informational"),
        ("ai powered business automation", "informational"),
        ("full stack development agency", "commercial"),
        ("white label software development", "commercial"),
        ("managed infrastructure service", "commercial"),
    ]

    for keyword, category in melanin_seeds:
        upsert_keyword(site["id"], keyword, source="seed", category=category, priority="high")
    print(f"   → {len(melanin_seeds)} seed keywords registered")

    # ── orthoflowsolutions.com ────────────────────────────────────────────────
    ortho_site = register_site("orthoflowsolutions.com", "sc-domain:orthoflowsolutions.com")
    print(f"✅ orthoflowsolutions.com registered (id={ortho_site['id']})")

    ortho_seeds = [
        ("orthodontic invoice processing", "commercial"),
        ("dental billing automation", "commercial"),
        ("orthodontic practice management software", "commercial"),
        ("ai invoice classification dental", "commercial"),
        ("quickbooks integration orthodontics", "commercial"),
        ("dental invoice software", "commercial"),
        ("orthodontic billing software", "commercial"),
        ("automate dental office billing", "informational"),
        ("orthoflow", "brand"),
        ("orthodontic accounts payable automation", "commercial"),
        ("dental practice efficiency", "informational"),
        ("best billing software orthodontist", "comparison"),
        ("how to reduce dental billing errors", "informational"),
        ("orthodontic office management tools", "commercial"),
        ("hipaa compliant billing software", "commercial"),
    ]

    for keyword, category in ortho_seeds:
        upsert_keyword(ortho_site["id"], keyword, source="seed", category=category, priority="high")
    print(f"   → {len(ortho_seeds)} seed keywords registered")

    print("\n✅ Both sites registered in SEO pipeline. Weekly analysis will run Sunday night.")


if __name__ == "__main__":
    main()
