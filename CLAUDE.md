# Will It Travel? Which US Shows Will Succeed in Australia

Portfolio project for the **Research & Audience Analysis Intern** role at NBCUniversal Global Distribution (Sydney).
That team licenses NBCU shows/films to networks and streamers in 200+ territories and supports sales,
marketing, programming and strategy with audience insights. Independent project — not affiliated with NBCUniversal.

**Goal:** a tool telling a TV sales team which NBCU shows to sell to which Australian platform group.

## Australian platform groups
1. **Free-to-air (FTA):** Seven, Nine, Ten, ABC, SBS
2. **BVOD (free streaming apps):** 7plus, 9Now, 10 Play, ABC iview, SBS On Demand
3. **Paid streamers (SVOD):** Stan, Foxtel/BINGE, Netflix, Prime Video

## Data (public sources only; respect terms; don't scrape aggressively)
- US: Nielsen Streaming Top 10 (weekly), Nielsen The Gauge (monthly platform share — context only)
- AU: OzTAM weekly top programs (FTA), VOZ (BVOD)
- AU paid-streamer proxy: Netflix official Top 10 for Australia (top10.netflix.com) — Stan/BINGE/Prime have no public charts (state as limitation)
- Enrichment: TMDB API (genre, format, original network, production companies)
- Keys in `.env` (`TMDB_API_KEY`, `ANTHROPIC_API_KEY`), loaded via python-dotenv. **Never print, log or commit them.**
- If a source can't be downloaded reliably, give the user exact files + links + save path under `data/raw/`.
- Time window: **Oct 2025 – Sep 2026** (12 months).

## Method rules
- Compare **rankings/percentiles, not raw numbers** (OzTAM = viewers per program; Nielsen = minutes watched).
- Title matching: TMDB ID first, fuzzy fallback; write uncertain matches to `data/processed/uncertain_matches.csv` for manual review.
- "What to sell next" must exclude titles already licensed in AU (e.g. Stan's multi-year NBCU deal incl. Peacock originals).

## Outputs
1. Tidy matched US/AU dataset per title  ← session 1
2. Travel score by genre/format × platform group  ← session 1
3. Excel workbook (clean data + PivotTable-ready tabs) + charts  ← session 1
4. Ranked "what to sell next" list of NBCU shows not yet visible in AU, matched to best platform group with evidence  ← session 2
5. AI pitch briefs per platform group (Claude API) → `outputs/briefs/`  ← session 2
6. 6-slide executive PowerPoint (python-pptx), leading with the recommendation  ← session 2
7. README: question, sources, method, findings, limitations, how to run, the line
   "This product uses the TMDB API but is not endorsed or certified by TMDB", and the non-affiliation note  ← session 2

## Layout
- `src/` scripts · `data/raw/` (gitignored) · `data/processed/` · `outputs/charts/` · `outputs/briefs/`
- Python venv in `.venv/`; `pip install -r requirements.txt`

## How to work with the user
- Give a step-by-step plan first and wait for approval.
- Build one step at a time, run it, show the result before moving on.
- Keep code simple and well-commented — the user must explain it in an interview.
- List uncertain title matches for manual checking.
- After analysis, give the 3 most useful findings for a sales exec in plain English.
- GitHub: https://github.com/Cathvin/will-it-travel (origin, branch `main`). Push after each major step.

## Status after session 1 (2026-10-04)
- Outputs 1–3 done: `data/processed/matched_titles.csv`, `travel_score.csv`, `outputs/will_it_travel.xlsx`, `outputs/charts/`.
- Pipeline: `.venv/bin/python src/run_all.py` (VOZ fetch is slow first time; cached after).
- Data reality: Nielsen has no archive → 1 live week + 12 weeks entered from cached Nielsen pages in `data/manual/nielsen_manual.csv`. Cross-checked vs independent trade press: 22/130 rows confirmed (top ranks of 10/12 weeks), 0 discrepancies; the `verified` column names the source per row. Full lists are paywalled (THR, Adweek). Week of 3 Nov 2025 unverified.
- User wants NO manual steps. Wayback Machine (web.archive.org) is network-blocked here and fetching archived copies via other hosts was refused by the safety classifier — don't retry; the 13-week Nielsen sample stands.
- VOZ: 361 daily Top 30s (Oct 1 2025 – Sep 26 2026), weekly = each program's best day.
- Manual match fixes live in `data/manual/match_overrides.csv` (set/exclude/origin). `titles_reviewed.csv` = corrected TMDB table; use it, not `titles_tmdb.csv`.
- NBCU flags: `is_nbcu` = NBCU studio (ownership evidence); `nbcu_check_rights` = aired on NBCU channel only.
- Key method choice: travel score = AU share of US-content chart space ÷ US chart share (rank-weighted). Netflix pickup reported for licensed titles only (originals launch globally).

## Status after session 2 (2026-10-04): ALL OUTPUTS DONE
- 4: `src/sell_next.py` -> `sell_next.csv` (Tier A chart hits first, Tier B TMDB-signal titles 2022–25), `sell_next_excluded.csv` (already on AU streaming per JustWatch/TMDB, Peacock originals, other streamers' originals), `sell_next_renewals.csv`.
- 5: `src/write_briefs.py` (claude-opus-5-5, server-side fallback "default") -> `outputs/briefs/*.md`.
- 6: `src/build_deck.py` (python-pptx, native charts, numbers read from CSVs) -> `outputs/will_it_travel_exec.pptx`.
- 7: `README.md`. Full pipeline: `src/run_all.py`. No LibreOffice on this machine: deck QA = validate.py + text-fit heuristic.
