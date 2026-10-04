# Will It Travel? Which US Shows Will Succeed in Australia

A tool that tells a TV sales team **which NBCUniversal shows to sell to which Australian channel or streaming service**, built from public audience data.

> **Independent portfolio project.** Not affiliated with, endorsed by or produced for NBCUniversal.
> This product uses the TMDB API but is not endorsed or certified by TMDB.
> Streaming availability data is provided by JustWatch (via TMDB).

---

## The question

When a US show or film is a hit in the US, will it also succeed in Australia, and **on which kind of platform**?

| Australian platform group | Who |
|---|---|
| 1. Free-to-air TV | Seven, Nine, Ten, ABC, SBS |
| 2. Free streaming apps (BVOD) | 7plus, 9Now, 10 Play, ABC iview, SBS On Demand |
| 3. Paid streamers | Stan, Foxtel/BINGE, Netflix, Prime Video |

## Key findings

1. **Free TV buys US crime procedurals, and almost nothing else.** US-made content wins just **2.6%** of free-to-air Top 30 slots (5.4% on the free apps). Half the chart is news, sport and live events. The US content that does get in is scripted crime series (*The Rookie*, *9-1-1*, *Murder in a Small Town*). **Scripted series score 343; films score 9.**
2. **On paid streaming, being a US hit isn't enough.** **91%** of Netflix originals that hit in the US also chart in Australia, but only **28%** of *licensed* US hits do. Licensed titles need a local deal, a local home and local promotion to break through.
3. **Paid streamers over-index on horror (134), comedy (118), documentary (116 by genre, 138 by format) and family animation; drama (65) and reality (50) lag.** Australians prefer local reality formats, so US reality is better sold as a format to remake locally.
4. **Most NBCU US hits are already licensed in Australia.** 31 of the 35 NBCU titles that charted in the US but not in Australia already have an Australian streaming home. The true white space is small (see `sell_next.csv`). The bigger opportunity is a **renewal watch-list**: 30 NBCU titles licensed here that never chart. *Law & Order*, *La Brea* and *All Her Fault* fit free-to-air better than their current homes.

## Outputs

| # | Output | Where |
|---|---|---|
| 1 | Tidy matched US/AU dataset per title | `data/processed/matched_titles.csv` (822 titles, 218 charted in both countries); every chart entry in `charts_long.csv` |
| 2 | Travel score by genre/format x platform group | `data/processed/travel_score.csv`, `netflix_pickup.csv`, `au_chart_mix.csv` |
| 3 | Excel workbook + charts | `outputs/will_it_travel.xlsx` (data and summary tabs are Excel Tables, ready for PivotTables) and `outputs/charts/*.png` |
| 4 | Ranked "what to sell next" list | `data/processed/sell_next.csv` (+ `sell_next_excluded.csv`, `sell_next_renewals.csv`) |
| 5 | AI pitch briefs per platform group | `outputs/briefs/free_to_air.md`, `bvod.md`, `paid_streaming.md` |
| 6 | 6-slide executive deck | `outputs/will_it_travel_exec.pptx` |

## Data sources (public only)

| Source | What we use | Coverage |
|---|---|---|
| [Nielsen Streaming Top 10](https://www.nielsen.com/data-center/top-ten/) | US streaming rank (minutes viewed) | 13 weeks: 1 live week + 12 weeks entered from cached Nielsen pages. 22 rows cross-checked against trade press (Adweek, TheWrap, Hollywood Reporter, TVLine) with 0 discrepancies; the source for each row is in `data/manual/nielsen_manual.csv` |
| [Netflix Top 10](https://www.netflix.com/tudum/top10/) | Weekly Top 10 for the US and Australia | All 52 weeks, Oct 2025 - Sep 2026 |
| [OzTAM VOZ](https://virtualoz.com.au/market-reports/) | Daily "Total TV Consolidated 7 Top 30 Programs": Total TV and BVOD average audience | 361 days, Oct 2025 - Sep 2026. Downloaded at robots.txt's 10-second crawl delay. *Source: OzTAM VOZ* |
| [TMDB API](https://www.themoviedb.org/) | Genre, format, origin country, networks, production companies | Every charting title |
| JustWatch via TMDB watch providers | Where each title is streaming in Australia today | Used to exclude already-licensed titles |
| [Nielsen The Gauge](https://www.nielsen.com/data-center/the-gauge/) | Context only (US platform share) | Not used in the scores |

## Method

1. **Collect** each source into one tidy table: one row = one title on one weekly chart (`charts_long.csv`).
   VOZ daily Top 30s become weekly charts using each program's best day of the week. Platform group 1 is ranked by Total TV average audience; group 2 re-ranks the same programs by BVOD average audience.
2. **Use rankings, not audiences.** Nielsen measures minutes watched; OzTAM measures average viewers. So each chart position becomes a **rank percentile** within its own chart (#1 = 1.0, #10 of 10 = 0.1, #30 of 30 = 0.033).
3. **Enrich** every title with TMDB: genre, format (film, scripted series, reality...), origin country and companies.
   NBCU ownership = an NBCU **production company** (Universal Television, Universal Pictures, DreamWorks Animation, Illumination, Focus Features, Carnival, Working Title...). Titles that only *aired* on an NBCU channel are flagged "check rights", not counted as owned.
4. **Match** US and Australian titles by TMDB ID, and link Australian local versions to US formats (*Love Island Australia* <-> *Love Island USA*). Uncertain matches were listed in `uncertain_matches.csv` and reviewed by hand; corrections are in `data/manual/match_overrides.csv`.
5. **Travel score** (per genre/format and platform group):
   `travel score = (genre's share of US-content chart points in the AU group) / (genre's share of US chart points) x 100`.
   Chart points are the sum of rank percentiles. **100** = the same share of chart space in Australia as in the US; above 100 = over-performs in Australia. Fewer than 3 Australian titles = not scored.
   A second lens, **same-title pickup**, measures the share of licensed US hits that also chart on Netflix Australia (Netflix originals are excluded because they launch globally).
6. **What to sell next**:
   - **Candidates:** NBCU titles that charted in the US but not in Australia (Tier A), plus NBCU titles from 2022-2025 with strong US audience signals on TMDB (Tier B, weaker evidence).
   - **Excluded:** titles already streaming in Australia, Peacock originals (covered by Stan's NBCU output deal), and originals of other streamers.
   - **Best platform group:** the group with the highest fit = format score x genre score / 100.
   - **Ranking:** by US strength x platform fit, with Tier A listed first.
7. **Pitch briefs**: Claude (`claude-opus-5-5`) writes one brief per platform group from a data pack of our own numbers, and is told not to invent any figures.

## Limitations

- **Free TV scores rest on few titles.** About 10 US titles reached the free-to-air or BVOD Top 30 in a year. Treat those scores as direction, not precision.
- **Stan, BINGE and Prime Video publish no charts.** Paid streaming uses Netflix Top 10 Australia as the proxy. A title "not visible in Australia" may be on Stan.
- **Nielsen is a sample:** 13 of 52 weeks. Its full archive isn't public, the Wayback Machine was unreachable from the build machine, and full weekly lists are paywalled. Netflix US (52 weeks) is the main like-for-like US signal.
- **Top 10/30 charts only show hits.** A title that is watched but never makes a chart is invisible to this analysis.
- **TMDB and JustWatch are crowd-sourced or commercial data.** Origin countries were wrong for several Australian shows (fixed by hand). Rights and availability should be confirmed with contracts.
- **VOZ figures are free-to-air Consolidated 7.** BVOD here means BVOD viewing of free-to-air programs in the Top 30, not all BVOD-only content.
- **Tier B evidence (TMDB popularity) is weaker than chart data**, and recent films may simply be in a cinema or first pay-TV window.

## How to run

```bash
git clone https://github.com/Cathvin/will-it-travel.git && cd will-it-travel
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Create `.env` with your own keys (it is gitignored, never commit it):

```
TMDB_API_KEY=...
ANTHROPIC_API_KEY=...
```

Download the Netflix file once, then run the pipeline:

```bash
curl -o data/raw/netflix_all_weeks_countries.tsv https://www.netflix.com/tudum/top10/data/all-weeks-countries.tsv
.venv/bin/python src/run_all.py
```

The first VOZ download takes about 1 hour (10-second crawl delay); later runs reuse the cached files.

| Script | Step |
|---|---|
| `src/fetch_nielsen.py`, `src/fetch_voz.py` | Collect Nielsen and VOZ charts |
| `src/load_data.py` | All sources -> `charts_long.csv` |
| `src/enrich_tmdb.py` | TMDB metadata + NBCU flags |
| `src/match_titles.py` | US <-> AU matching (applies `data/manual/match_overrides.csv`) |
| `src/travel_score.py` | Travel score tables |
| `src/build_outputs.py` | Excel workbook + charts |
| `src/sell_next.py` | What-to-sell-next list |
| `src/write_briefs.py` | Claude pitch briefs |
| `src/build_deck.py` | Executive PowerPoint |

## Project structure

```
src/              pipeline scripts
data/raw/         downloaded source files (gitignored)
data/manual/      hand-entered Nielsen weeks and reviewed match corrections
data/processed/   tidy outputs
outputs/          workbook, charts/, briefs/, deck
```

---
This product uses the TMDB API but is not endorsed or certified by TMDB. This is an independent project, not affiliated with NBCUniversal.
