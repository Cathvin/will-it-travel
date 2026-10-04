"""
Load every chart source into ONE tidy table: one row = one title on one weekly chart.

Output: data/processed/charts_long.csv with columns
  market          US or AU
  source          nielsen | netflix | voz
  platform_group  US: "US streaming (Nielsen)" / "US Netflix"
                  AU: "1 Free-to-air" / "2 BVOD" / "3 Paid streaming (Netflix AU)"
  chart           which list (e.g. Overall, TV, Films, Total TV, BVOD)
  week_start      Monday of the chart week (Netflix weeks are stored by their end date, Sunday)
  title, rank, chart_size
  rank_pct        rank as a percentile within its own chart: 1.0 = #1, near 0 = bottom.
                  This is what lets us compare Nielsen minutes with OzTAM viewers fairly:
                  we never compare raw numbers, only "how high up its own chart was it?"
  measure, value  the raw number and what it means (kept for reference only)

Run:  .venv/bin/python src/load_data.py
"""
import re
from io import StringIO
from pathlib import Path

import pandas as pd

START, END = "2025-10-01", "2026-09-30"
RAW = Path("data/raw")
OUT = Path("data/processed/charts_long.csv")


def rank_percentile(rank, chart_size):
    """#1 of 10 -> 1.0, #10 of 10 -> 0.1. Same scale for a top 10 and a top 30."""
    return (chart_size - rank + 1) / chart_size


# ---------------------------------------------------------------- Netflix
def load_netflix():
    """Official Netflix Top 10 (all countries). We keep the US and Australia."""
    df = pd.read_csv(RAW / "netflix_all_weeks_countries.tsv", sep="\t")
    df = df[df.country_iso2.isin(["US", "AU"]) & df.week.between(START, END)].copy()
    out = pd.DataFrame({
        "market": df.country_iso2,
        "source": "netflix",
        "platform_group": df.country_iso2.map({"US": "US Netflix", "AU": "3 Paid streaming (Netflix AU)"}),
        "chart": df.category,  # "TV" or "Films"
        # Netflix labels each week by its last day (Sunday); move to Monday to line up with Nielsen
        "week_start": (pd.to_datetime(df.week) - pd.Timedelta(days=6)).dt.date,
        "title": df.show_title,
        "season": df.season_title,
        "rank": df.weekly_rank,
        "chart_size": 10,
        "measure": "Netflix weekly rank (views)",
        "value": pd.NA,
    })
    return out


# ---------------------------------------------------------------- Nielsen
def load_nielsen():
    """Nielsen US Streaming Top 10: live/archived pages + hand-entered weeks."""
    parts = [pd.read_csv(RAW / "nielsen_auto.csv"), pd.read_csv("data/manual/nielsen_manual.csv")]
    df = pd.concat(parts, ignore_index=True)
    # If the same week+list appears twice (auto and manual), keep the auto version
    df = df.drop_duplicates(subset=["week_start", "list", "rank"], keep="first")
    out = pd.DataFrame({
        "market": "US",
        "source": "nielsen",
        "platform_group": "US streaming (Nielsen)",
        "chart": df["list"],
        "week_start": pd.to_datetime(df.week_start).dt.date,
        "title": df.title,
        "season": pd.NA,
        "rank": df["rank"],
        "chart_size": 10,
        "measure": "minutes viewed (millions)",
        "value": df.minutes_millions,
    })
    return out


# ---------------------------------------------------------------- VOZ (OzTAM)
def clean_voz_title(raw):
    """
    VOZ program names carry broadcast tags. Strip them so episodes of the same show group together:
      'M- A FEW GOOD MEN (R)'  -> 'A FEW GOOD MEN'   (M- = movie, (R) = repeat)
      'HARD QUIZ S10-EV'       -> 'HARD QUIZ'
      'RFDS-EP.2'              -> 'RFDS'
      'TIPPING POINT UK -RPT'  -> 'TIPPING POINT UK'
      'HOME AND AWAY EP.2'     -> 'HOME AND AWAY'
      'BIG BROTHER AUSTRALIA – LAUNCH' -> 'BIG BROTHER AUSTRALIA'
    """
    t = raw.upper().strip()
    t = re.sub(r"^M-\s*", "", t)                         # movie prefix
    t = re.sub(r"\(R\)", "", t)                          # repeat marker
    t = re.sub(r"\s+[-–].*$", "", t)                     # ' -PREVIEW', ' – LAUNCH' (space before dash = a tag)
    t = re.sub(r"-(EV|AM|PM|SA|NT|EP\.?\s*\d+|RPT)\b.*$", "", t)  # '-EV', '-EP.2' glued to the title
    t = re.sub(r"\s+EP\.?\s*\d+$", "", t)                # ' EP.2'
    t = re.sub(r"\b(RPT|MON|TUE|WED|THU|FRI|SAT|SUN)$", "", t.strip())
    t = re.sub(r"\s+S\d+$", "", t.strip())               # season number
    return re.sub(r"\s+", " ", t).strip(" -")


def load_voz():
    """
    VOZ daily Top 30 (Total People table) -> weekly charts for two platform groups:
      1 Free-to-air : ranked by Total TV average audience
      2 BVOD        : ranked by BVOD average audience
    Weekly rule (simple and explainable): each program's BEST day of the week counts,
    then programs are re-ranked within the week and the top 30 kept.
    """
    daily = []
    for path in sorted((RAW / "voz").glob("c7_top30_*.html")):
        day = pd.to_datetime(path.stem.replace("c7_top30_", ""))
        table = pd.read_html(StringIO(path.read_text(encoding="utf-8")))[0]  # first table = Total People
        table.columns = ["rank", "raw_title", "network", "reach", "tt_avg", "bvod_avg"]
        table["date"] = day
        daily.append(table)
    df = pd.concat(daily, ignore_index=True)

    for col in ["reach", "tt_avg", "bvod_avg"]:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")
    df["is_movie"] = df.raw_title.str.upper().str.startswith("M-")
    df["title"] = df.raw_title.map(clean_voz_title)
    df["week_start"] = (df.date - pd.to_timedelta(df.date.dt.weekday, unit="D")).dt.date  # Monday

    out = []
    for group, col in [("1 Free-to-air", "tt_avg"), ("2 BVOD", "bvod_avg")]:
        best = (df.groupby(["week_start", "title"], as_index=False)
                  .agg(value=(col, "max"), network=("network", "first"), is_movie=("is_movie", "max")))
        best["rank"] = best.groupby("week_start")["value"].rank(ascending=False, method="first").astype(int)
        best = best[best["rank"] <= 30]
        out.append(pd.DataFrame({
            "market": "AU", "source": "voz", "platform_group": group,
            "chart": "Total TV" if col == "tt_avg" else "BVOD",
            "week_start": best.week_start, "title": best.title, "season": pd.NA,
            "rank": best["rank"], "chart_size": 30,
            "measure": "Total TV avg audience" if col == "tt_avg" else "BVOD avg audience",
            "value": best.value, "network": best.network, "is_movie": best.is_movie,
        }))
    return pd.concat(out, ignore_index=True)


def main():
    charts = pd.concat([load_netflix(), load_nielsen(), load_voz()], ignore_index=True)
    charts["rank_pct"] = rank_percentile(charts["rank"], charts["chart_size"]).round(3)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    charts.to_csv(OUT, index=False)

    print(f"Saved {len(charts):,} chart rows -> {OUT}\n")
    summary = charts.groupby(["market", "platform_group"]).agg(
        rows=("title", "size"), weeks=("week_start", "nunique"), unique_titles=("title", "nunique"))
    print(summary.to_string())


if __name__ == "__main__":
    main()
