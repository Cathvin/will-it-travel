"""
Step 5: match US and Australian chart performance per title  (OUTPUT 1).

Matching rules, in order:
  1. Same TMDB ID  -> same title. (Netflix "Stranger Things" and Nielsen "Stranger Things"
     both resolve to TMDB TV 66732, so they match even if the spelling differs slightly.)
  2. Same FORMAT   -> a local remake of a US format, e.g. "LOVE ISLAND AUSTRALIA" <-> "Love Island USA".
     We strip country words (Australia, USA, UK...) and compare what's left.
     These links are always sent for manual review.

Uncertain matches (TMDB name score < 85, or any format link) are written to
data/processed/uncertain_matches.csv for a human to check. Corrections go in
data/manual/match_overrides.csv (columns: title, action, tmdb_id, media_type, origin_country, note)
and are applied on the next run.

Outputs: data/processed/matched_titles.csv  (one row per title family)
         data/processed/titles_reviewed.csv (TMDB table with manual corrections applied)

Run:  .venv/bin/python src/match_titles.py
"""
import re
from pathlib import Path

import pandas as pd

from enrich_tmdb import NBCU_NETWORKS, NBCU_STUDIOS, describe_format, details, first_match

UNCERTAIN_BELOW = 85
OVERRIDES = Path("data/manual/match_overrides.csv")
COUNTRY_WORDS = r"\b(australia|aus|au|usa|us|uk|nz|america|american|britain|british)\b"

GROUPS = {  # platform_group -> short column prefix
    "US streaming (Nielsen)": "us_nielsen",
    "US Netflix": "us_netflix",
    "1 Free-to-air": "au_fta",
    "2 BVOD": "au_bvod",
    "3 Paid streaming (Netflix AU)": "au_svod",
}


def tmdb_details(tmdb_id, media):
    """Re-describe a title from a TMDB ID chosen by hand (same fields as enrich_tmdb.py)."""
    d = details(tmdb_id, media)
    genres = [g["name"] for g in d.get("genres", [])]
    networks = [n["name"] for n in d.get("networks", [])]
    companies = [c["name"] for c in d.get("production_companies", [])]
    studio, network = first_match(companies, NBCU_STUDIOS), first_match(networks, NBCU_NETWORKS)
    return {
        "tmdb_id": tmdb_id, "media_type": media, "tmdb_name": d.get("name") or d.get("title"),
        "year": (d.get("first_air_date") or d.get("release_date") or "")[:4],
        "genres": "|".join(genres), "primary_genre": genres[0] if genres else "Unknown",
        "format": describe_format(media, d, genres),
        "origin_country": "|".join(d.get("origin_country", []) or [c["iso_3166_1"] for c in d.get("production_countries", [])]),
        "original_language": d.get("original_language"), "networks": "|".join(networks),
        "production_companies": "|".join(companies), "nbcu_studio": studio, "nbcu_network": network,
        "is_nbcu": bool(studio), "nbcu_check_rights": bool(network) and not studio,
    }


def format_key(title):
    """'LOVE ISLAND AUSTRALIA' and 'Love Island USA' -> 'love island'."""
    t = re.sub(r"\(\d{4}\)", "", str(title).lower())
    t = re.sub(COUNTRY_WORDS, "", t)
    t = re.sub(r"[^a-z0-9 ]", "", t.replace("&", "and"))
    return re.sub(r"\s+", " ", t).strip()


def main():
    charts = pd.read_csv("data/processed/charts_long.csv")
    tmdb = pd.read_csv("data/processed/titles_tmdb.csv")

    # Apply manual corrections, if any. Columns: title, action, tmdb_id, media_type, origin_country, note
    #   action = set      -> point the title at a different TMDB entry (and/or fix its origin country)
    #   action = exclude  -> drop it (live sport, or a wrong match with no correct TMDB entry)
    if OVERRIDES.exists():
        fix = pd.read_csv(OVERRIDES, dtype=str).fillna("")
        tmdb = tmdb.astype(object).set_index("title")  # object dtype so any value can be written
        for r in fix.itertuples():
            if r.title not in tmdb.index:
                print(f"  override skipped (title not found): {r.title}")
                continue
            if r.action == "exclude":
                tmdb.loc[r.title, "category"] = "excluded by review"
                continue
            if r.tmdb_id:
                d = tmdb_details(int(r.tmdb_id), r.media_type)
                tmdb.loc[r.title, list(d)] = list(d.values())
            if r.origin_country:
                tmdb.loc[r.title, "origin_country"] = r.origin_country
            tmdb.loc[r.title, ["match_score", "category"]] = [100, "programming"]
        tmdb = tmdb.reset_index()
        tmdb["match_score"] = pd.to_numeric(tmdb.match_score)
        tmdb["tmdb_id"] = pd.to_numeric(tmdb.tmdb_id)
        print(f"Applied {len(fix)} manual overrides from {OVERRIDES}")

    # Save the reviewed title table so later steps use the corrected matches
    tmdb.to_csv("data/processed/titles_reviewed.csv", index=False)

    prog = tmdb[tmdb.category == "programming"].copy()
    prog["tmdb_key"] = prog.media_type + ":" + prog.tmdb_id.astype(int).astype(str)
    prog["format_key"] = prog.title.map(format_key)

    # ---- Rule 2: format links. If an AU-only title shares a format_key with a US title,
    # point it at the US title's TMDB key (the "family").
    us_keys = prog[prog.markets.str.contains("US")].drop_duplicates("format_key").set_index("format_key").tmdb_key
    prog["family_key"] = prog.tmdb_key
    prog["link_type"] = "same TMDB title"
    au_only = (prog.markets == "AU") & prog.format_key.isin(us_keys.index) & (prog.tmdb_key != prog.format_key.map(us_keys))
    prog.loc[au_only, "family_key"] = prog.loc[au_only, "format_key"].map(us_keys)
    prog.loc[au_only, "link_type"] = "local format version"

    # ---- Attach family key to every chart row, then summarise per family x platform group
    charts = charts.merge(prog[["title", "family_key"]], on="title", how="inner")
    agg = charts.groupby(["family_key", "platform_group"]).agg(
        weeks=("week_start", "nunique"), best_pct=("rank_pct", "max"), avg_pct=("rank_pct", "mean"), best_rank=("rank", "min"),
    ).reset_index()
    wide = agg.pivot(index="family_key", columns="platform_group")
    wide.columns = [f"{GROUPS[g]}_{m}" for m, g in wide.columns]
    wide = wide.reset_index()

    # ---- Title descriptors come from the family's "main" title (prefer the US one)
    prog["is_us"] = prog.markets.str.contains("US")
    main_rows = prog.sort_values(["is_us", "match_score"], ascending=False).drop_duplicates("family_key")
    keep = ["family_key", "tmdb_id", "media_type", "tmdb_name", "year", "primary_genre", "genres", "format",
            "origin_country", "original_language", "networks", "production_companies", "is_nbcu", "nbcu_studio", "nbcu_network", "nbcu_check_rights"]
    titles_in_family = prog.groupby("family_key").title.agg(lambda s: " | ".join(sorted(set(s)))).rename("chart_titles")
    link = prog.groupby("family_key").link_type.agg(lambda s: "local format version" if (s == "local format version").any() else "same TMDB title")

    out = main_rows[keep].merge(titles_in_family, on="family_key").merge(link, on="family_key").merge(wide, on="family_key", how="left")

    # Simple yes/no flags for each platform group
    for prefix in GROUPS.values():
        out[f"{prefix}_charted"] = out[f"{prefix}_weeks"].fillna(0) > 0
    out["in_us"] = out.us_nielsen_charted | out.us_netflix_charted
    out["in_au"] = out.au_fta_charted | out.au_bvod_charted | out.au_svod_charted
    out["is_us_origin"] = out.origin_country.fillna("").str.contains("US")

    out = out.sort_values(["in_us", "in_au", "us_nielsen_weeks", "us_netflix_weeks"], ascending=False)
    out.to_csv("data/processed/matched_titles.csv", index=False)

    # ---- Uncertain matches for manual review
    # Also uncertain: a series from an AU TV chart (VOZ) matched to a NON-Australian TMDB entry.
    # Often right (The Rookie airs on Seven) but sometimes it's a local version with the same name.
    au_tv_foreign = (prog.sources == "voz") & (prog.media_type == "tv") & ~prog.origin_country.fillna("").str.contains("AU")
    prog.loc[au_tv_foreign & (prog.link_type == "same TMDB title"), "link_type"] = "AU chart -> non-AU series"
    uncertain = prog[(prog.match_score < UNCERTAIN_BELOW) | (prog.link_type != "same TMDB title")]
    uncertain = uncertain[["title", "markets", "sources", "tmdb_name", "year", "media_type", "tmdb_id", "match_score", "link_type", "family_key"]]
    uncertain = uncertain.sort_values(["link_type", "match_score"])
    uncertain.to_csv("data/processed/uncertain_matches.csv", index=False)

    print(f"Matched titles (families): {len(out)}")
    print(f"  charted in US: {out.in_us.sum()}  |  in AU: {out.in_au.sum()}  |  BOTH: {(out.in_us & out.in_au).sum()}")
    print(f"  local format versions linked: {(out.link_type == 'local format version').sum()}")
    print(f"  NBCU-owned: {out.is_nbcu.sum()}  (of which charted in both: {(out.is_nbcu & out.in_us & out.in_au).sum()})")
    print(f"Uncertain matches to review: {len(uncertain)} -> data/processed/uncertain_matches.csv")


if __name__ == "__main__":
    main()
