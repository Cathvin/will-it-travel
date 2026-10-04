"""
Download VOZ (OzTAM) "Total TV Consolidated 7 Top 30 Programs" daily reports.

Source: https://virtualoz.com.au/market-reports/  (Source: OzTAM VOZ)
Each daily page lists Australia's top 30 free-to-air programs for that day, with
Total TV reach, Total TV average audience and BVOD (free streaming app) average audience.

Politeness rules we follow:
- robots.txt asks for a 10-second crawl delay, so we wait 10 seconds between requests.
- Pages already downloaded are skipped, so re-running the script never re-downloads.

Raw HTML is saved to data/raw/voz/ (gitignored). Parsing happens in load_voz.py.

Run:  .venv/bin/python src/fetch_voz.py
"""
import time
from datetime import date, timedelta
from pathlib import Path

import requests

# Study window (see CLAUDE.md)
START = date(2025, 10, 1)
END = date(2026, 9, 30)

URL = "https://virtualoz.com.au/report/total-tv-consolidated-7-top-30-programs/?date={d}"
OUT_DIR = Path("data/raw/voz")
DELAY_SECONDS = 10  # from virtualoz.com.au/robots.txt
HEADERS = {"User-Agent": "Mozilla/5.0 (independent portfolio research project)"}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    day = START
    while day <= END:
        out_file = OUT_DIR / f"c7_top30_{day.isoformat()}.html"
        if out_file.exists():
            day += timedelta(days=1)
            continue  # already have it

        try:
            resp = requests.get(URL.format(d=day.isoformat()), headers=HEADERS, timeout=30)
            if resp.status_code == 200 and "<table" in resp.text:
                out_file.write_text(resp.text, encoding="utf-8")
                print(f"{day}  saved")
            else:
                print(f"{day}  no data (HTTP {resp.status_code})")
        except requests.RequestException as err:
            print(f"{day}  failed: {err}")

        time.sleep(DELAY_SECONDS)
        day += timedelta(days=1)

    print("Done. Files:", len(list(OUT_DIR.glob("*.html"))))


if __name__ == "__main__":
    main()
