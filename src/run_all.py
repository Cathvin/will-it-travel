"""
Run the whole pipeline in order.

  1. fetch_nielsen.py   Nielsen US Streaming Top 10 (live page + saved pages)
  2. fetch_voz.py       OzTAM VOZ daily top 30s (slow: ~1 hour first time, then skips existing files)
  3. load_data.py       all sources -> data/processed/charts_long.csv
  4. enrich_tmdb.py     TMDB metadata + NBCU flags -> titles_tmdb.csv
  5. match_titles.py    US <-> AU matching -> matched_titles.csv + uncertain_matches.csv
  6. travel_score.py    travel score tables
  7. sell_next.py       ranked "what to sell next" list (output 4)
  8. build_outputs.py   Excel workbook + charts
  9. write_briefs.py    Claude pitch briefs (output 5)
 10. build_deck.py      executive PowerPoint (output 6)

The Netflix Top 10 file is downloaded once by hand or with:
  curl -o data/raw/netflix_all_weeks_countries.tsv https://www.netflix.com/tudum/top10/data/all-weeks-countries.tsv

Run:  .venv/bin/python src/run_all.py
"""
import subprocess
import sys

STEPS = ["fetch_nielsen.py", "fetch_voz.py", "load_data.py", "enrich_tmdb.py",
         "match_titles.py", "travel_score.py", "sell_next.py", "build_outputs.py",
         "write_briefs.py", "build_deck.py"]

for step in STEPS:
    print(f"\n=== {step} ===")
    subprocess.run([sys.executable, f"src/{step}"], check=True)
