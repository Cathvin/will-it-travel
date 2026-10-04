"""
Collect Nielsen US Streaming Top 10 lists (ranked by minutes viewed, persons 2+).

Nielsen's page (https://www.nielsen.com/data-center/top-ten/) only shows the latest
week and has no archive, so we combine:
  1. the live page (latest week), and
  2. Internet Archive (Wayback Machine) snapshots of the same page from our study window.
Months with no snapshot are filled by hand in data/raw/nielsen_manual.csv (see README).

The page has four streaming tables, always in this order:
  Overall, Original, Acquired, Movies.
We save one tidy CSV: data/raw/nielsen_auto.csv

Run:  .venv/bin/python src/fetch_nielsen.py
"""
import html
import re
import time
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

LIVE_URL = "https://www.nielsen.com/data-center/top-ten/"
# Snapshot timestamps found via https://archive.org/wayback/available (one per month checked).
# "id_" asks the Wayback Machine for the original HTML without its toolbar.
WAYBACK_SNAPSHOTS = ["20251010161404", "20260215170932", "20260716110321", "20260916162802"]
WAYBACK_URL = "https://web.archive.org/web/{ts}id_/https://www.nielsen.com/data-center/top-ten/"

LIST_NAMES = ["Overall", "Original", "Acquired", "Movies"]
HEADERS = {"User-Agent": "Mozilla/5.0 (independent portfolio research project)"}
OUT_FILE = Path("data/raw/nielsen_auto.csv")
# Any Nielsen Top 10 pages saved by hand (browser "Save Page As > HTML only") go here
SAVED_PAGES_DIR = Path("data/raw/nielsen_pages")


def parse_page(page_html, source_url):
    """Turn one saved Nielsen page into tidy rows: week, list, rank, title, minutes, provider."""
    # The streaming week label looks like "Sep. 14 – Sep. 20, 2026" and is the first
    # date range on the page (the linear TV charts below say "Week of ...").
    text = html.unescape(page_html)  # turns "&#8211;" into a real dash
    week_match = re.search(r"([A-Z][a-z]{2,4}\.? \d{1,2}) [–-] ([A-Z][a-z]{2,4}\.? \d{1,2}, (20\d\d))", text)
    week_label = f"{week_match.group(1)} – {week_match.group(2)}"
    # Week start date: first half of the label plus the year (handles "Sept."/"June" etc.)
    start_text = week_match.group(1).replace(".", "").replace("Sept", "Sep") + " " + week_match.group(3)
    week_start = pd.to_datetime(start_text, format="mixed")

    tables = pd.read_html(StringIO(page_html))
    # Keep only the streaming tables (they have a "Minutes (Millions)" column)
    streaming = [t for t in tables if any("Minutes" in str(c) for c in t.columns)][:4]

    rows = []
    for list_name, table in zip(LIST_NAMES, streaming):
        for _, r in table.iterrows():
            rows.append({
                "week_start": week_start.date(),
                "week_label": week_label,
                "list": list_name,
                "rank": int(r["Rank"]),
                "title": str(r["Program Name"]).strip(),
                "minutes_millions": float(str(r["Minutes (Millions)"]).replace(",", "")),
                "episodes": r.get("# of Episodes"),
                "provider": r["Streaming Provider(s)"],
                "source_url": source_url,
            })
    return rows


def main():
    all_rows = []

    # 1) Live page + Wayback snapshots. A failed download is skipped, not fatal.
    urls = [LIVE_URL] + [WAYBACK_URL.format(ts=ts) for ts in WAYBACK_SNAPSHOTS]
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as err:
            print(f"SKIPPED (could not download): {url}  [{type(err).__name__}]")
            continue
        rows = parse_page(resp.text, url)
        print(f"{rows[0]['week_label']:<28} {len(rows)} rows  <- {url}")
        all_rows.extend(rows)
        time.sleep(3)  # be polite

    # 2) Pages saved by hand
    SAVED_PAGES_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(SAVED_PAGES_DIR.glob("*.htm*")):
        rows = parse_page(path.read_text(encoding="utf-8", errors="ignore"), f"saved file: {path.name}")
        print(f"{rows[0]['week_label']:<28} {len(rows)} rows  <- {path}")
        all_rows.extend(rows)

    df = pd.DataFrame(all_rows).drop_duplicates(subset=["week_start", "list", "rank"])
    df.to_csv(OUT_FILE, index=False)
    print(f"Saved {len(df)} rows, {df.week_start.nunique()} weeks -> {OUT_FILE}")


if __name__ == "__main__":
    main()
