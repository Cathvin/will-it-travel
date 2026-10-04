"""
Enrich every charting title with TMDB metadata: genre, format, original network,
production companies, country and year. Also flags NBCUniversal-owned titles.

This product uses the TMDB API but is not endorsed or certified by TMDB.

How a title is matched:
  1. Search TMDB (TV or movie, depending on what the chart tells us).
  2. Score each result by how similar its name is to our title (0-100, rapidfuzz),
     with a small bonus for TMDB popularity to break ties.
  3. Keep the best result and its score. Low scores are reviewed by hand later.

API responses are cached in data/raw/tmdb_cache.json, so re-running is fast and
doesn't hit the API again. The API key is read from .env and never printed.

Input : data/processed/charts_long.csv
Output: data/processed/titles_tmdb.csv  (one row per unique chart title)

Run:  .venv/bin/python src/enrich_tmdb.py
"""
import json
import os
import re
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from rapidfuzz import fuzz

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
API_KEY = os.getenv("TMDB_API_KEY")
BASE = "https://api.themoviedb.org/3"
CACHE_FILE = Path("data/raw/tmdb_cache.json")
OUT = Path("data/processed/titles_tmdb.csv")

# VOZ top 30s are full of news, sport and live events. They are not licensable US content,
# so we label them and skip the TMDB lookup (otherwise "9NEWS" might match a random show).
NOT_PROGRAMMING = re.compile(
    r"NEWS|NRL|AFL|FOOTBALL|SOCCER|CRICKET|TENNIS|RUGBY|BLEDISLOE|MELBOURNE CUP|GRAND FINAL|"
    r"OLYMPIC|COMMONWEALTH|STATE OF ORIGIN|SUNRISE|^TODAY|THE MORNING SHOW|A CURRENT AFFAIR|"
    r"^7\.30|60 MINUTES|INSIDERS|FOUR CORNERS|MEDIA WATCH|THE PROJECT|LIVE|CAROLS|COUNTDOWN|"
    r"ANZAC|AUSTRALIA DAY|NEW YEAR|ELECTION|BUDGET|PARLIAMENT|WEATHER|CUP|STATE CUP|PLANET AMERICA"
)
# Live sport/events can appear on any chart (e.g. WWE on Netflix). Skip them everywhere.
LIVE_SPORT = re.compile(r"\bWWE\b|ROYAL RUMBLE|SUPERCARS|BATHURST|CHAMPIONSHIPS?\b| VS\. ", re.I)

# Two different questions, so two lists (names as they appear on TMDB):
# 1) STUDIOS: NBCUniversal-owned production companies -> evidence NBCU owns/distributes the title.
#    (Sky is part of Comcast with NBCU; NBCU Global Distribution sells Sky Studios content.)
NBCU_STUDIOS = [
    "Universal Television", "Universal Content Productions", "UCP", "Universal Pictures",
    "Universal International Studios", "Universal Television Alternative Studio", "Universal Studio Group",
    "NBCUniversal", "NBC Universal", "NBC Studios", "NBC Productions", "NBC News Studios",
    "Focus Features", "DreamWorks Animation", "Illumination", "Working Title Films", "Carnival Films",
    "Sky Studios", "Wolf Entertainment", "Wolf Films", "Telemundo Studios",
    "Matchbox Pictures",  # NBCU's Australian studio
    "Monkey Kingdom",
]
# 2) NETWORKS: NBCU-owned channels/streamers. Airing on NBC does NOT mean NBCU owns the rights
#    (e.g. Friends aired on NBC but is a Warner Bros show), so this is only a "check rights" flag.
NBCU_NETWORKS = ["NBC", "Peacock", "Bravo", "USA Network", "Syfy", "E!", "Oxygen", "CNBC", "MSNBC",
                 "Telemundo", "Universal Kids", "Sky Atlantic", "Sky One", "Sky Max", "Sky Comedy", "Sky Showcase"]


def first_match(names, candidates):
    """Return the first name that equals or starts with one of the candidates ('' if none)."""
    for name in names:
        for c in candidates:
            if name == c or name.startswith(c + " "):
                return name
    return ""


# ---------------------------------------------------------------- API + cache
def load_cache():
    return json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}


CACHE = load_cache()


def tmdb_get(path, **params):
    """GET from TMDB with caching. The key is sent as a parameter and never stored in the cache."""
    cache_key = path + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    if cache_key not in CACHE:
        resp = requests.get(BASE + path, params={**params, "api_key": API_KEY}, timeout=30)
        resp.raise_for_status()
        CACHE[cache_key] = resp.json()
        time.sleep(0.05)  # TMDB allows ~40 req/s; we stay far below
    return CACHE[cache_key]


def save_cache():
    CACHE_FILE.write_text(json.dumps(CACHE))


# ---------------------------------------------------------------- matching
def normalise(title):
    """Lowercase, drop years like '(2025)' and punctuation, for fair name comparison."""
    t = re.sub(r"\(\d{4}\)", "", str(title).lower())
    t = t.replace("&", "and")
    return re.sub(r"[^a-z0-9 ]", "", t).strip()


def best_match(title, media_types, prefer_au=False):
    """Search TMDB for `title` in the given media types; return (result, media_type, score).
    prefer_au: the title comes from an Australian TV chart, so when two versions share a name
    (e.g. "The Voice" US vs "The Voice" AU) we favour the Australian one."""
    year = re.search(r"\((\d{4})\)", str(title))
    query = re.sub(r"\(\d{4}\)", "", str(title)).strip()
    best, best_type, best_score = None, None, 0
    for media in media_types:
        results = tmdb_get(f"/search/{media}", query=query).get("results", [])[:10]
        for r in results:
            name = r.get("name") or r.get("title") or ""
            original = r.get("original_name") or r.get("original_title") or ""
            score = max(fuzz.ratio(normalise(title), normalise(name)),
                        fuzz.ratio(normalise(title), normalise(original)))
            # Year in the title, e.g. "Frankenstein (2025)": reward the right year
            date = r.get("first_air_date") or r.get("release_date") or ""
            if year and date[:4] == year.group(1):
                score += 10
            score += min(r.get("popularity", 0), 100) / 50  # tiny tie-breaker (max +2)
            if prefer_au and "AU" in r.get("origin_country", []):
                score += 5
            if score > best_score:
                best, best_type, best_score = r, media, score
    return best, best_type, min(round(best_score), 100)


def details(tmdb_id, media):
    return tmdb_get(f"/{media}/{tmdb_id}")


def describe_format(media, d, genres):
    """A simple format label a sales team would use."""
    if media == "movie":
        return "Animated film" if "Animation" in genres else "Film"
    tv_type = d.get("type", "")  # TMDB TV types: Scripted, Reality, Documentary, Miniseries, Talk Show, News...
    if tv_type == "Reality" or "Reality" in genres:
        return "Reality / unscripted"
    if tv_type == "Documentary" or "Documentary" in genres:
        return "Documentary"
    if tv_type == "Talk Show" or "Talk" in genres:
        return "Talk / variety"
    if "Animation" in genres:
        return "Animated series"
    if tv_type == "Miniseries":
        return "Scripted limited series"
    return "Scripted series"


def main():
    charts = pd.read_csv("data/processed/charts_long.csv")
    # What kind of title is it? Use the chart it appeared on.
    charts["is_film"] = (charts.chart.isin(["Films", "Movies"])) | (charts.get("is_movie", False) == True)
    titles = charts.groupby("title").agg(
        markets=("market", lambda s: "|".join(sorted(set(s)))),
        sources=("source", lambda s: "|".join(sorted(set(s)))),
        any_film=("is_film", "max"), all_film=("is_film", "min"),
    ).reset_index()

    rows = []
    for i, t in enumerate(titles.itertuples(), start=1):
        row = {"title": t.title, "markets": t.markets, "sources": t.sources}
        if (t.sources == "voz" and NOT_PROGRAMMING.search(t.title.upper())) or LIVE_SPORT.search(t.title):
            row.update(category="news/sport/live", match_score=None)
            rows.append(row)
            continue

        media_types = ["movie"] if t.all_film else (["tv", "movie"] if t.any_film else ["tv"])
        if t.sources == "voz" and not t.any_film:
            media_types = ["tv", "movie"]  # VOZ only marks films with "M-", so allow both
        from_au_tv = t.sources == "voz"
        result, media, score = best_match(t.title, media_types, prefer_au=from_au_tv)
        if result is None or score < 75:
            # Retry without country words and subtitles: "THE 1% CLUB UK" -> "THE 1% CLUB",
            # "THE AMAZING RACE AUSTRALIA: CELEBRITY" -> "THE AMAZING RACE"
            simpler = re.sub(r"\b(AUSTRALIA|UK|USA|NZ)\b.*$", "", t.title, flags=re.I).split(":")[0].strip()
            if simpler and simpler.lower() != t.title.lower():
                r2, m2, s2 = best_match(simpler, media_types, prefer_au=from_au_tv)
                if r2 is not None and s2 >= score:
                    result, media, score = r2, m2, min(s2, 80)  # cap: a simplified match always gets reviewed
        if result is None:
            row.update(category="no TMDB result", match_score=0)
            rows.append(row)
            continue

        d = details(result["id"], media)
        genres = [g["name"] for g in d.get("genres", [])]
        networks = [n["name"] for n in d.get("networks", [])]
        companies = [c["name"] for c in d.get("production_companies", [])]
        studio = first_match(companies, NBCU_STUDIOS)
        network = first_match(networks, NBCU_NETWORKS)
        row.update(
            category="programming",
            tmdb_id=result["id"], media_type=media, tmdb_name=d.get("name") or d.get("title"),
            match_score=score,
            year=(d.get("first_air_date") or d.get("release_date") or "")[:4],
            genres="|".join(genres), primary_genre=genres[0] if genres else "Unknown",
            format=describe_format(media, d, genres),
            origin_country="|".join(d.get("origin_country", []) or [c["iso_3166_1"] for c in d.get("production_countries", [])]),
            original_language=d.get("original_language"),
            networks="|".join(networks), production_companies="|".join(companies),
            nbcu_studio=studio,                 # e.g. "Universal Television" (blank if none)
            nbcu_network=network,               # e.g. "NBC" (blank if none)
            is_nbcu=bool(studio),               # ownership evidence = NBCU studio
            nbcu_check_rights=bool(network) and not studio,  # aired on NBCU channel, owner unclear
        )
        rows.append(row)
        if i % 50 == 0:
            print(f"  {i}/{len(titles)} titles looked up")
            save_cache()

    save_cache()
    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    print(f"\nSaved {len(out)} titles -> {OUT}")
    print(out.category.value_counts().to_string())
    prog = out[out.category == "programming"]
    print(f"\nMatch score: >=90: {(prog.match_score >= 90).sum()}  |  75-89: {prog.match_score.between(75, 89).sum()}  |  <75: {(prog.match_score < 75).sum()}")
    print(f"NBCU studio titles: {prog.is_nbcu.sum()}  |  aired on NBCU network only (check rights): {prog.nbcu_check_rights.sum()}")


if __name__ == "__main__":
    main()
