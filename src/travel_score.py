"""
Step 6: the TRAVEL SCORE  (OUTPUT 2).

Question: when a US show is a hit in the US, how likely is it to also chart in Australia,
and in which platform group? And which genres/formats travel best?

We only use RANKINGS (as percentiles), never raw audience numbers, because
Nielsen measures minutes watched and OzTAM measures average viewers per program.

Two lenses, both built only from rank percentiles:

A) TRAVEL SCORE (headline, works for all 3 platform groups)
   "Of the chart space US-made content wins in Australia, how much goes to each genre,
    compared with that genre's share of the US charts?"
     chart points  = sum of rank percentiles (a #1 counts 1.0, a #10 of 10 counts 0.1)
     AU share      = genre's chart points / all US-origin chart points in that AU group
     US share      = genre's chart points / all chart points in the US charts
     travel_score  = AU share / US share x 100
   100 = the genre gets the same share of chart space in AU as in the US.
   200 = it punches twice above its US weight in AU; 50 = half.
   Why this lens? Free-to-air and BVOD rarely air THIS YEAR'S US streaming hits, but US
   content still wins ~12% of their top-30 slots (mostly films and library series).
   This lens captures that; a "same title" lens would not.

B) SAME-TITLE PICKUP (Netflix AU only, where US hits actually show up)
   Licensed titles only: Netflix originals launch globally, so they would inflate pickup.
   hit_rate  = share of a genre's licensed US hits that also charted on Netflix AU
   rank_gap  = AU rank percentile minus US rank percentile for titles in both
               (positive = ranks higher in AU than in the US)

Outputs (data/processed/):
  title_travel.csv        one row per US hit, with its US and AU performance
  travel_score.csv        lens A: genre/format x platform group
  netflix_pickup.csv      lens B: same-title pickup on Netflix AU
  au_chart_mix.csv        where AU chart slots come from (AU / US / UK ... content), by group

Run:  .venv/bin/python src/travel_score.py
"""
import pandas as pd

K = 5            # lens B: shrink small genres towards 100 (strength, in titles)
MIN_TITLES = 5   # lens B: below this, a segment is flagged "small sample"
AU_GROUPS = {"au_fta": "1 Free-to-air", "au_bvod": "2 BVOD", "au_svod": "3 Paid streaming (Netflix AU)"}


def sales_genre(genres):
    """Collapse TMDB's TV + film genre lists into one genre a sales team would use.
    Rules are checked in order, so 'Animation|Comedy' -> Family & Animation."""
    g = set(str(genres).split("|"))
    rules = [
        ("Reality", {"Reality"}),
        ("Documentary", {"Documentary"}),
        ("Family & Animation", {"Animation", "Kids", "Family"}),
        ("Horror", {"Horror"}),
        ("Crime & Thriller", {"Crime", "Thriller", "Mystery"}),
        ("Sci-Fi & Fantasy", {"Sci-Fi & Fantasy", "Science Fiction", "Fantasy"}),
        ("Action & Adventure", {"Action & Adventure", "Action", "Adventure", "War", "War & Politics", "Western"}),
        ("Comedy", {"Comedy"}),
        ("Romance", {"Romance"}),
        ("Drama", {"Drama"}),
    ]
    for name, keys in rules:
        if g & keys:
            return name
    return "Other"


def share_scores(charts, segment_col):
    """Lens A: rank-weighted share of chart space, AU group vs US."""
    us = charts[charts.market == "US"]
    us_share = us.groupby(segment_col).rank_pct.sum() / us.rank_pct.sum()
    rows = []
    for group in AU_GROUPS.values():
        au = charts[(charts.platform_group == group) & charts.is_us_origin]
        au_points = au.groupby(segment_col).rank_pct.sum()
        au_titles = au.groupby(segment_col).title.nunique()
        for seg in sorted(set(us_share.index) | set(au_points.index)):
            a = au_points.get(seg, 0) / au.rank_pct.sum() if len(au) else 0
            u = us_share.get(seg, 0)
            n = int(au_titles.get(seg, 0))
            rows.append({
                "segment_type": segment_col.replace("sales_", ""), "segment": seg, "platform_group": group,
                "au_share_of_us_content": round(a, 4), "us_chart_share": round(u, 4),
                "travel_score": round(100 * a / u) if u > 0 else None,
                "au_titles": n, "small_sample": n < 3,
                "example_titles": ", ".join(au[au[segment_col] == seg].groupby("title").rank_pct.sum()
                                            .sort_values(ascending=False).index[:3].str.title()),
            })
    return pd.DataFrame(rows)


def segment_scores(df, segment_col):
    """Lens B: same-title pickup on Netflix AU."""
    rows = []
    for prefix, group in [("au_svod", AU_GROUPS["au_svod"])]:
        charted = df[f"{prefix}_charted"]
        overall_rate = charted.mean()
        for seg, sub in df.groupby(segment_col):
            hit = sub[f"{prefix}_charted"]
            both = sub[hit]
            n, k = len(sub), int(hit.sum())
            rate = k / n
            index = 100 * rate / overall_rate if overall_rate > 0 else None
            gap = (both[f"{prefix}_avg_pct"] - both["us_avg_pct"]).mean() if k else None
            rows.append({
                "segment_type": segment_col.replace("sales_", ""),
                "segment": seg,
                "platform_group": group,
                "us_hits": n,
                "travelled": k,
                "hit_rate": round(rate, 3),
                "pickup_index": round((n * index + K * 100) / (n + K)) if index is not None else None,  # shrunk to 100 for small n
                "avg_rank_gap": round(gap, 3) if gap is not None else None,
                "small_sample": n < MIN_TITLES,
                "example_titles": ", ".join(both.sort_values(f"{prefix}_avg_pct", ascending=False).tmdb_name.head(3)),
            })
    return pd.DataFrame(rows)


def main():
    m = pd.read_csv("data/processed/matched_titles.csv")
    m["sales_genre"] = m.genres.map(sales_genre)

    # US performance = average rank percentile across the US charts it appeared on
    m["us_avg_pct"] = m[["us_nielsen_avg_pct", "us_netflix_avg_pct"]].mean(axis=1)
    m["us_weeks"] = m[["us_nielsen_weeks", "us_netflix_weeks"]].fillna(0).sum(axis=1)

    # Netflix originals launch worldwide on the same day, so they "travel" automatically.
    # Licensed titles (made by someone else, e.g. an NBCU show on Netflix US) are what a
    # distributor actually sells, so we report them separately.
    m["is_netflix_original"] = m.networks.fillna("").str.split("|").apply(lambda n: "Netflix" in n) | \
                               m.production_companies.fillna("").str.contains("Netflix")
    us_hits = m[m.in_us & m.is_us_origin].copy()
    print(f"US hits (US-origin titles charting in the US): {len(us_hits)}")
    for prefix, group in AU_GROUPS.items():
        print(f"  also charted in {group:<32}: {us_hits[f'{prefix}_charted'].sum():>4}  ({us_hits[f'{prefix}_charted'].mean():.0%})")

    # Title-level table (useful evidence for the sales list in session 2)
    cols = ["tmdb_name", "year", "media_type", "format", "sales_genre", "is_netflix_original", "is_nbcu", "nbcu_studio", "nbcu_check_rights",
            "networks", "us_weeks", "us_avg_pct", "us_nielsen_weeks", "us_netflix_weeks"]
    for prefix in AU_GROUPS:
        cols += [f"{prefix}_charted", f"{prefix}_weeks", f"{prefix}_avg_pct"]
    title_travel = us_hits[cols].copy()
    for prefix in AU_GROUPS:
        title_travel[f"{prefix}_rank_gap"] = (title_travel[f"{prefix}_avg_pct"] - title_travel.us_avg_pct).round(3)
    title_travel["au_groups_charted"] = title_travel[[f"{p}_charted" for p in AU_GROUPS]].sum(axis=1)
    title_travel.sort_values(["au_groups_charted", "us_weeks"], ascending=False).to_csv("data/processed/title_travel.csv", index=False)

    # Chart-level table with genre/format attached (for lens A)
    charts = pd.read_csv("data/processed/charts_long.csv")
    tmdb = pd.read_csv("data/processed/titles_reviewed.csv")  # includes manual corrections
    tmdb["sales_genre"] = tmdb.genres.map(sales_genre)
    tmdb["is_us_origin"] = tmdb.origin_country.fillna("").str.contains("US")
    charts = charts.merge(tmdb[["title", "category", "origin_country", "is_us_origin", "sales_genre", "format"]], on="title", how="left")
    prog = charts[charts.category == "programming"]

    scores = pd.concat([share_scores(prog, "sales_genre"), share_scores(prog, "format")], ignore_index=True)
    scores.to_csv("data/processed/travel_score.csv", index=False)
    licensed = us_hits[~us_hits.is_netflix_original]
    pickup = pd.concat([segment_scores(licensed, "sales_genre"), segment_scores(licensed, "format")], ignore_index=True)
    orig = us_hits[us_hits.is_netflix_original]
    print(f"\nNetflix AU pickup: Netflix originals {orig.au_svod_charted.mean():.0%} (n={len(orig)})  vs  "
          f"licensed titles {licensed.au_svod_charted.mean():.0%} (n={len(licensed)})")
    pickup.to_csv("data/processed/netflix_pickup.csv", index=False)

    # Where do AU chart slots come from? (all AU chart rows)
    au = charts[charts.market == "AU"].copy()
    au["origin"] = au.origin_country.fillna("").str.split("|").str[0].replace("", "Unknown")
    au.loc[au.category == "news/sport/live", "origin"] = "News / sport / live (AU)"
    au["origin"] = au.origin.where(au.origin.isin(["AU", "US", "GB", "News / sport / live (AU)"]), "Other")
    mix = (au.groupby(["platform_group", "origin"]).size().rename("chart_slots").reset_index())
    mix["share"] = (mix.chart_slots / mix.groupby("platform_group").chart_slots.transform("sum")).round(3)
    mix.to_csv("data/processed/au_chart_mix.csv", index=False)

    # Print the headline tables
    print("\nTRAVEL SCORE by genre (100 = same share of chart space in AU as in US; * = fewer than 3 AU titles)")
    tbl = scores[scores.segment_type == "genre"].copy()
    tbl["cell"] = tbl.travel_score.astype("Int64").astype(str) + tbl.small_sample.map({True: "*", False: ""})
    print(tbl.pivot(index="segment", columns="platform_group", values="cell").to_string())
    print("\nTRAVEL SCORE by format")
    tbl = scores[scores.segment_type == "format"].copy()
    tbl["cell"] = tbl.travel_score.astype("Int64").astype(str) + tbl.small_sample.map({True: "*", False: ""})
    print(tbl.pivot(index="segment", columns="platform_group", values="cell").to_string())
    print("\nNETFLIX AU same-title pickup by genre, LICENSED titles (hit rate; index 100 = average)")
    print(pickup[pickup.segment_type == "genre"][["segment", "us_hits", "travelled", "hit_rate", "pickup_index", "avg_rank_gap"]].to_string(index=False))
    print("\nAU chart slots by content origin")
    print(mix.pivot(index="origin", columns="platform_group", values="share").fillna(0).to_string())


if __name__ == "__main__":
    main()
