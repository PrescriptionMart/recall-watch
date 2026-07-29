"""Fetch FDA's recall announcement feed and save it as alerts.json.

These announcements appear days or weeks before the classified entry
shows up in the enforcement database, so the page uses them as early
alerts. Public data only. Runs on a schedule via GitHub Actions.

Usage: fetch_alerts.py [source]
  source: optional feed URL or local file path, for testing the parser.
"""
import json
import re
import sys
import email.utils
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

FEED_URL = "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/recalls/rss.xml"
OUT = Path(__file__).resolve().parents[2] / "alerts.json"
KEEP_DAYS = 60
MAX_ITEMS = 100


def fetch(source):
    if source and not source.startswith("http"):
        return Path(source).read_text(encoding="utf-8")
    req = urllib.request.Request(
        source or FEED_URL,
        headers={"User-Agent": "PrescriptionMart-RecallWatch/1.0 (public recall feed reader)"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def strip_html(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def parse(xml_text):
    root = ET.fromstring(xml_text)
    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    items = []
    for item in root.iter("item"):
        title = strip_html(item.findtext("title", ""))
        link = (item.findtext("link", "") or "").strip()
        summary = strip_html(item.findtext("description", ""))[:400]
        pub = item.findtext("pubDate", "")
        try:
            when = email.utils.parsedate_to_datetime(pub)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        if when < cutoff or not title:
            continue
        items.append({
            "title": title,
            "link": link,
            "date": when.strftime("%Y-%m-%d"),
            "summary": summary,
        })
    items.sort(key=lambda i: i["date"], reverse=True)
    return items[:MAX_ITEMS]


def main():
    source = sys.argv[1] if len(sys.argv) > 1 else None
    items = parse(fetch(source))
    payload = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "items": items,
    }
    OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(items)} items to {OUT}")


if __name__ == "__main__":
    main()
