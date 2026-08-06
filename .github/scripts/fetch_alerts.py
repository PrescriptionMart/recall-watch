"""Fetch FDA's recall announcement feed and save it as alerts.json.

These announcements appear days or weeks before the classified entry
shows up in the enforcement database, so the page uses them as early
alerts. Public data only. Runs on a schedule via GitHub Actions.

Tries each candidate feed in order and uses the first one that parses
with items. If every candidate fails, it lists the feed links on FDA's
RSS directory page in the log so the next fix is quick.

Usage: fetch_alerts.py [source]
  source: optional feed URL or local file path, for testing the parser.
"""
import json
import re
import sys
import time
import email.utils
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

# FDA's own site blocks automated readers (fake 404s to datacenter IPs,
# confirmed 2026-07-29), so the early-alert source is a news feed search.
# News coverage is also what actually drives the phone calls.
CANDIDATE_FEEDS = [
    "https://news.google.com/rss/search?q=FDA+drug+recall&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=%22recall%22%20when:7d%20FDA&hl=en-US&gl=US&ceid=US:en",
]
PROBE_URLS = [
    "https://www.fda.gov/",
    "https://api.fda.gov/drug/enforcement.json?limit=1",
    "https://content.govdelivery.com/accounts/USFDA/bulletins.rss",
    "https://content.govdelivery.com/accounts/USFDA/topics/USFDA_48/feed.rss",
    "https://news.google.com/rss/search?q=FDA+drug+recall&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=%22recall%22%20when:7d%20FDA&hl=en-US&gl=US&ceid=US:en",
]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
OUT = Path(__file__).resolve().parents[2] / "alerts.json"
KEEP_DAYS = 60
MAX_ITEMS = 100


def http_get(url, attempts=3):
    """GET with retries. Retries transient failures (timeouts, connection
    errors, 429, 5xx) with a growing pause. Permanent errors like 404 fail
    immediately."""
    last_err = None
    for attempt in range(attempts):
        if attempt:
            time.sleep(5 * (2 ** (attempt - 1)))  # 5s, then 10s
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                last_err = e
                print(f"  transient HTTP {e.code}, attempt {attempt + 1} of {attempts}")
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            print(f"  network error ({e}), attempt {attempt + 1} of {attempts}")
            continue
    raise last_err


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


def probe_directory():
    print("All candidates failed. Probing alternative sources:")
    for url in PROBE_URLS:
        print("trying:", url)
        try:
            body = http_get(url)
        except Exception as e:
            print("  failed:", e)
            continue
        try:
            items = parse(body)
            print("  OK, parses as a feed with", len(items), "recent items")
            for it in items[:3]:
                print("    item:", it["date"], "|", it["title"][:120])
        except Exception:
            print("  OK but not a feed; first 150 chars:", body[:150].replace("\n", " "))


def main():
    if len(sys.argv) > 1:
        source = sys.argv[1]
        text = http_get(source) if source.startswith("http") else Path(source).read_text(encoding="utf-8")
        items = parse(text)
    else:
        items = None
        for url in CANDIDATE_FEEDS:
            try:
                candidate_items = parse(http_get(url))
            except Exception as e:
                print(f"candidate failed: {url} ({e})")
                continue
            print(f"using feed: {url} ({len(candidate_items)} items)")
            items = candidate_items
            break
        if items is None:
            # Every source failed even after retries. If the saved data is
            # recent, keep it and exit clean: the next scheduled run gets
            # another shot and nobody needs a failure email over a blip.
            # Only fail loudly when the data is genuinely going stale.
            if OUT.exists():
                try:
                    saved = json.loads(OUT.read_text(encoding="utf-8"))
                    updated = datetime.strptime(saved["updated"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    age_hours = (datetime.now(timezone.utc) - updated).total_seconds() / 3600
                    if age_hours < 48:
                        print(f"fetch failed, keeping saved data ({age_hours:.0f}h old); will retry next run")
                        sys.exit(0)
                    print(f"fetch failed and saved data is {age_hours:.0f}h old, flagging for attention")
                except (ValueError, KeyError) as e:
                    print("fetch failed and saved data unreadable:", e)
            probe_directory()
            sys.exit(1)

    # Only recall stories. The query is broad enough to catch drug news
    # that has nothing to do with recalls.
    items = [i for i in items if "recall" in i["title"].lower()]

    payload = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "items": items,
    }
    OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(items)} items to {OUT}")


if __name__ == "__main__":
    main()
