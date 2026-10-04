"""
Output 4: ranked "WHAT TO SELL NEXT" list.

Which NBCUniversal-owned titles are proven in the US but not yet visible in Australia,
and which Australian platform group should we pitch each one to?

1. CANDIDATES: titles made by an NBCU studio (Universal Television, Universal Pictures,
   DreamWorks Animation, Illumination, Focus Features...) that charted in the US
   (Nielsen or Netflix US Top 10) but never charted in Australia.
2. EXCLUDE titles that are already licensed or not ours to sell:
   - already streaming in Australia on a subscription/free service (TMDB watch-provider
     data, powered by JustWatch) - e.g. on Stan, Netflix, BINGE, Prime Video
   - Peacock originals: covered by Stan's multi-year NBCUniversal output deal
   - originals of another streamer (Netflix, Apple TV, Prime Video...): that streamer
     holds worldwide rights even if an NBCU studio made it
3. BEST PLATFORM GROUP: the group where the title's format and genre have the highest
   travel score (from travel_score.py; small samples ignored).
4. RANK by opportunity = US strength x platform fit.
     US strength (0-100) = average of (a) its average US chart percentile and
                           (b) weeks in US Top 10s, capped at 8 weeks
     platform fit        = best (format score x genre score / 100) / 100, capped at 3

TIER B (wider net): the chart data only covers ~35 NBCU titles, and most are already
licensed. So we also scan TMDB for NBCU-studio titles released since 2022 that have a strong
US audience signal (TMDB popularity + votes) and NO Australian streaming home. Tier B evidence
is weaker than chart data, so its US strength is capped at 60 and Tier A is always listed first.
2026 releases are skipped (still in cinemas or the first pay-TV window, so not "unsold").

RENEWAL WATCH-LIST: NBCU titles that ARE licensed in Australia but never chart there, where
the current home is not the best-fit platform group -> worth re-pitching at renewal.

Outputs: data/processed/sell_next.csv, sell_next_excluded.csv, sell_next_renewals.csv

Run:  .venv/bin/python src/sell_next.py
"""
import pandas as pd

from enrich_tmdb import save_cache, tmdb_get
from match_titles import tmdb_details
from travel_score import sales_genre

# TMDB company IDs for NBCU studios (looked up with /search/company)
NBCU_TV_COMPANIES = [26727, 7938, 42141, 6196, 10163, 25545, 135346, 95155, 87455]  # Universal TV, UCP, DreamWorks TV, Carnival, Working Title, Wolf, Sky Studios, NBCU Intl
NBCU_FILM_COMPANIES = [33, 521, 6704, 10146, 221513, 10163]                          # Universal Pictures, DreamWorks, Illumination, Focus, Working Title
PAID = {"Stan", "BINGE", "Foxtel Now", "Netflix", "Amazon Prime Video", "Disney Plus", "Paramount Plus", "Apple TV", "Hayu"}
FREE_APPS = {"7plus", "9Now", "10 Play", "ABC iview", "SBS On Demand"}

GROUPS = ["1 Free-to-air", "2 BVOD", "3 Paid streaming (Netflix AU)"]
GROUP_LABEL = {"1 Free-to-air": "Free-to-air (Seven, Nine, Ten, ABC, SBS)",
               "2 BVOD": "Free streaming apps (7plus, 9Now, 10 Play, iview, SBS On Demand)",
               "3 Paid streaming (Netflix AU)": "Paid streamers (Stan, BINGE, Netflix, Prime Video)"}
OTHER_STREAMER_ORIGINALS = ["Netflix", "Apple TV", "Apple TV+", "Prime Video", "Amazon", "Disney+", "Hulu", "HBO Max", "Max", "Paramount+"]


def au_providers(tmdb_id, media):
    """Where can Australians watch this today? Returns the AU subscription/free providers (JustWatch data via TMDB)."""
    data = tmdb_get(f"/{media}/{int(tmdb_id)}/watch/providers").get("results", {}).get("AU", {})
    names = [p["provider_name"] for kind in ("flatrate", "free", "ads") for p in data.get(kind, [])]
    return sorted(set(names))


def main():
    m = pd.read_csv("data/processed/matched_titles.csv")
    tt = pd.read_csv("data/processed/title_travel.csv")[["tmdb_name", "year", "sales_genre", "us_avg_pct", "us_weeks"]]
    scores = pd.read_csv("data/processed/travel_score.csv")

    cand = m[(m.is_nbcu == True) & m.in_us & ~m.in_au].merge(tt, on=["tmdb_name", "year"], how="left")
    print(f"NBCU titles that charted in the US but not in Australia: {len(cand)}")

    # ---- Exclusions
    rows = []
    for c in cand.itertuples():
        networks = str(c.networks) if pd.notna(c.networks) else ""
        providers = au_providers(c.tmdb_id, c.media_type)
        reason = ""
        if "Peacock" in networks.split("|"):
            reason = "Peacock original - covered by Stan's NBCU output deal"
        elif any(s in networks.split("|") for s in OTHER_STREAMER_ORIGINALS):
            reason = f"Original of another streamer ({networks}) - not NBCU's to license"
        elif providers:
            reason = "Already streaming in Australia on " + ", ".join(providers)
        rows.append({**c._asdict(), "au_streaming_now": ", ".join(providers), "excluded_reason": reason})
    save_cache()
    df = pd.DataFrame(rows).drop(columns=["Index"])
    excluded = df[df.excluded_reason != ""]
    df = df[df.excluded_reason == ""].copy()
    print(f"Excluded as already licensed / not ours: {len(excluded)}  ->  remaining opportunities: {len(df)}")

    df["tier"] = "A: US chart hit"

    # ---- Tier B: NBCU titles since 2022 with a strong US signal and no AU streaming home
    seen = set(m.tmdb_id.dropna().astype(int))
    tier_b = []
    for media, companies, date_key in [("tv", NBCU_TV_COMPANIES, "first_air_date.gte"), ("movie", NBCU_FILM_COMPANIES, "primary_release_date.gte")]:
        for page in (1, 2, 3):
            res = tmdb_get(f"/discover/{media}", **{"with_companies": "|".join(map(str, companies)), date_key: "2022-01-01",
                                                    "sort_by": "popularity.desc", "vote_count.gte": 50, "page": page})
            for r in res.get("results", []):
                release = r.get("first_air_date") or r.get("release_date") or ""
                # Skip 2026 releases: still in cinemas / first pay-TV window, not "unsold"
                if r["id"] in seen or r.get("original_language") != "en" or release >= "2026-01-01":
                    continue
                seen.add(r["id"])
                d = tmdb_details(r["id"], media)
                if not d["is_nbcu"]:
                    continue
                nets = d["networks"].split("|") if d["networks"] else []
                comps = d["production_companies"]
                providers = au_providers(r["id"], media)
                if "Peacock" in nets:
                    reason = "Peacock original - covered by Stan's NBCU output deal"
                elif any(x in nets for x in OTHER_STREAMER_ORIGINALS) or any(x in comps for x in ["Netflix", "Amazon MGM Studios", "Apple Studios", "Apple Original Films"]):
                    reason = "Original of another streamer - not NBCU's to license"
                elif providers:
                    reason = "Already streaming in Australia on " + ", ".join(providers)
                else:
                    reason = ""
                row = {**d, "sales_genre": sales_genre(d["genres"]), "popularity": r.get("popularity", 0),
                       "vote_count": r.get("vote_count", 0), "au_streaming_now": ", ".join(providers), "excluded_reason": reason,
                       "us_nielsen_weeks": 0, "us_netflix_weeks": 0, "tier": "B: strong US signal (TMDB)"}
                tier_b.append(row)
    save_cache()
    tier_b = pd.DataFrame(tier_b)
    excluded = pd.concat([excluded, tier_b[tier_b.excluded_reason != ""]], ignore_index=True)
    tier_b = tier_b[tier_b.excluded_reason == ""].copy()
    # US strength for tier B: popularity percentile within the tier, capped at 60 (weaker evidence than charts)
    tier_b["us_strength_b"] = (60 * tier_b.popularity.rank(pct=True)).round(1)
    print(f"Tier B (TMDB scan, no AU home): {len(tier_b)} more opportunities")
    df = pd.concat([df, tier_b], ignore_index=True)

    # ---- Platform fit from the travel score (ignore small samples)
    valid = scores[~scores.small_sample]
    lookup = {(r.segment_type, r.segment, r.platform_group): r for r in valid.itertuples()}

    def fit(row, group):
        """Format is the main driver (films hardly travel to free-to-air, whatever the genre);
        genre adjusts it up or down. fit = format score x genre score / 100."""
        fmt = lookup.get(("format", row.format, group))
        gen = lookup.get(("genre", row.sales_genre, group))
        if fmt is None:
            return gen.travel_score if gen is not None else None
        return fmt.travel_score * (gen.travel_score / 100 if gen is not None else 1)

    for g in GROUPS:
        df[f"fit_{g[:1]}"] = df.apply(lambda r: fit(r, g), axis=1)
    fit_cols = [f"fit_{g[:1]}" for g in GROUPS]
    df["best_group"] = df[fit_cols].idxmax(axis=1).map({f"fit_{g[:1]}": g for g in GROUPS})
    df["best_fit"] = df[fit_cols].max(axis=1)

    # ---- Opportunity score
    df["us_strength"] = (100 * (0.5 * df.us_avg_pct.fillna(0) + 0.5 * df.us_weeks.fillna(0).clip(upper=8) / 8)).round(1)
    if "us_strength_b" in df:
        df["us_strength"] = df.us_strength_b.where(df.tier.str.startswith("B"), df.us_strength)
    df["opportunity_score"] = (df.us_strength * (df.best_fit.clip(upper=300) / 100)).round(1)

    # ---- Evidence, in plain English
    def evidence(r):
        us_parts = []
        if r.tier.startswith("B"):
            text = (f"US: no Top 10 week in our sample, but strong TMDB audience signal (popularity {r.popularity:.0f}, "
                    f"{int(r.vote_count)} votes). AU: no Australian streaming home found. ")
            return text + fit_text(r)
        if r.us_nielsen_weeks > 0:
            us_parts.append(f"{int(r.us_nielsen_weeks)} wk(s) in Nielsen Top 10")
        if r.us_netflix_weeks > 0:
            us_parts.append(f"{int(r.us_netflix_weeks)} wk(s) in Netflix US Top 10")
        text = f"US: {' + '.join(us_parts)}, best rank #{int(min(r.us_nielsen_best_rank if pd.notna(r.us_nielsen_best_rank) else 99, r.us_netflix_best_rank if pd.notna(r.us_netflix_best_rank) else 99))}. "
        text += "AU: never in an Australian Top 10/30 and no Australian streaming home found. "
        return text + fit_text(r)

    def fit_text(r):
        g = r.best_group
        fmt = lookup.get(("format", r.format, g))
        gen = lookup.get(("genre", r.sales_genre, g))
        text = ""
        fits = []
        if fmt is not None:
            fits.append(f"{r.format} scores {int(fmt.travel_score)} on {g[2:]}")
        if gen is not None:
            fits.append(f"{r.sales_genre} scores {int(gen.travel_score)}")
        text += "Fit: " + "; ".join(fits) + "."
        examples = (gen.example_titles if gen is not None else "") or (fmt.example_titles if fmt is not None else "")
        if examples:
            text += f" Comparable AU hits: {examples}."
        return text

    df["evidence"] = df.apply(evidence, axis=1)
    df["pitch_to"] = df.best_group.map(GROUP_LABEL)
    # Proven chart hits (tier A) first, then tier B; each ranked by opportunity score
    df = df.sort_values(["tier", "opportunity_score"], ascending=[True, False])
    df.insert(0, "rank", range(1, len(df) + 1))

    out_cols = ["rank", "tier", "tmdb_name", "year", "media_type", "format", "sales_genre", "nbcu_studio", "networks",
                "us_strength", "best_group", "pitch_to", "best_fit", "opportunity_score", "evidence"]
    df[out_cols].to_csv("data/processed/sell_next.csv", index=False)
    excluded[["tmdb_name", "year", "media_type", "networks", "au_streaming_now", "excluded_reason"]].drop_duplicates("tmdb_name").to_csv(
        "data/processed/sell_next_excluded.csv", index=False)

    # ---- Renewal watch-list: licensed in AU, never charted, current home != best-fit group
    ren = excluded[excluded.excluded_reason.str.startswith("Already streaming")].copy()
    ren = ren[ren.tier.fillna("A").astype(str).str.startswith("A")]  # chart-proven titles only
    def home_group(p):
        names = set(x.strip() for x in str(p).split(","))
        if names & FREE_APPS:
            return "2 BVOD"
        return "3 Paid streaming (Netflix AU)" if names else ""
    ren["current_group"] = ren.au_streaming_now.map(home_group)
    ren["sales_genre"] = ren.genres.map(sales_genre)
    for g in GROUPS:
        ren[f"fit_{g[:1]}"] = ren.apply(lambda r: fit(r, g), axis=1)
    ren["best_group"] = ren[fit_cols].idxmax(axis=1).map({f"fit_{g[:1]}": g for g in GROUPS})
    ren["note"] = ren.apply(lambda r: "Re-pitch to " + GROUP_LABEL[r.best_group] + " at renewal" if r.best_group != r.current_group
                            else "Right platform group but not charting - needs marketing support", axis=1)
    ren[["tmdb_name", "year", "format", "sales_genre", "au_streaming_now", "current_group", "best_group", "note"]].to_csv(
        "data/processed/sell_next_renewals.csv", index=False)
    print(f"Renewal watch-list: {len(ren)} licensed-but-not-charting titles, {(ren.best_group != ren.current_group).sum()} in a sub-optimal platform group")

    print("\nWHAT TO SELL NEXT (top 15)")
    print(df[["rank", "tier", "tmdb_name", "format", "sales_genre", "best_group", "opportunity_score"]].head(15).to_string(index=False))
    print(f"\nBy platform group: {df.best_group.value_counts().to_dict()}")
    print(f"Excluded total: {len(excluded)}  ({excluded.excluded_reason.str.split(' - ').str[0].str[:30].value_counts().to_dict()})")


if __name__ == "__main__":
    main()
