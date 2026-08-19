#!/usr/bin/env python3
"""One-shot test: register site + pull GSC data."""
import sys
sys.path.insert(0, "/app")

from integrations.seo.models import register_site, get_gsc_data, get_keywords
from integrations.seo.gsc import GSCConnector

# 1. Register the site
site = register_site("melanin-tech.com", "sc-domain:melanin-tech.com")
print(f"✅ Site registered: id={site['id']}, domain={site['domain']}")

# 2. Pull GSC data
try:
    gsc = GSCConnector("melanin-tech")
    rows = gsc.collect_weekly_data("melanin-tech.com")
    print(f"✅ Collected {rows} rows from GSC (last 28 days)")
except Exception as e:
    print(f"⚠️  GSC pull failed: {e}")
    rows = 0

# 3. Check what we got
if rows > 0:
    data = get_gsc_data(site["id"], limit=10)
    print(f"\nTop queries by impressions:")
    for row in data[:10]:
        print(f"  • \"{row['query']}\" — pos {row['position']:.1f}, {row['impressions']} imp, {row['clicks']} clicks")

    keywords = get_keywords(site["id"])
    print(f"\n✅ {len(keywords)} keywords auto-discovered from GSC")
