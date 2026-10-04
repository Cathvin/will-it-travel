"""
Step 7: Excel workbook + charts  (OUTPUT 3).

Charts  -> outputs/charts/*.png
Workbook -> outputs/will_it_travel.xlsx
  README            what each tab is, sources, method
  travel_score      genre/format x AU platform group (travel_score is a live Excel formula)
  netflix_pickup    same-title pickup on Netflix AU (hit_rate is a live formula)
  au_chart_mix      where AU chart slots come from
  title_travel      one row per US hit with US and AU performance
  matched_titles    one row per title family (output 1)
  charts_long       every chart row (best tab for your own PivotTables)
  uncertain_matches matches flagged for manual review
  charts            the PNG charts
Every data tab is an Excel Table (Insert > PivotTable works straight away).

Run:  .venv/bin/python src/build_outputs.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # draw to files, no window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

P = Path("data/processed")
CHARTS = Path("outputs/charts")
XLSX = Path("outputs/will_it_travel.xlsx")

# Colours (validated reference palette: categorical order + blue<->red diverging, grey midpoint)
TEXT, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
DIVERGING = LinearSegmentedColormap.from_list("travel", ["#e34948", "#f0efec", "#2a78d6"])  # red=travels worse, blue=better
GROUP_SHORT = {"1 Free-to-air": "Free-to-air", "2 BVOD": "BVOD (free apps)", "3 Paid streaming (Netflix AU)": "Paid streaming\n(Netflix AU)"}

plt.rcParams.update({"font.family": "Arial", "font.size": 10, "text.color": TEXT,
                     "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED})


def heatmap(scores, segment_type, filename, title):
    """Travel score grid. Cells with fewer than 3 AU titles are greyed out with a dash."""
    d = scores[scores.segment_type == segment_type]
    grid = d.pivot(index="segment", columns="platform_group", values="travel_score")
    small = d.pivot(index="segment", columns="platform_group", values="small_sample").fillna(True).astype(bool)
    grid = grid.loc[grid["3 Paid streaming (Netflix AU)"].sort_values(ascending=False).index]
    small = small.loc[grid.index]

    shown = grid.mask(small)  # hide small samples from the colour scale
    fig, ax = plt.subplots(figsize=(7.5, 0.42 * len(grid) + 1.6))
    norm = TwoSlopeNorm(vmin=0, vcenter=100, vmax=max(200, np.nanmax(shown.values) if shown.notna().any().any() else 200))
    ax.imshow(np.clip(shown.values.astype(float), 0, norm.vmax), cmap=DIVERGING, norm=norm, aspect="auto")
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            if small.iat[i, j]:
                ax.text(j, i, "–", ha="center", va="center", color=MUTED)
            else:
                ax.text(j, i, f"{grid.iat[i, j]:.0f}", ha="center", va="center", color=TEXT, fontweight="bold")
    ax.set_xticks(range(grid.shape[1]), [GROUP_SHORT[c] for c in grid.columns])
    ax.set_yticks(range(grid.shape[0]), grid.index)
    ax.set_xticks(np.arange(-.5, grid.shape[1]), minor=True)
    ax.set_yticks(np.arange(-.5, grid.shape[0]), minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="both", length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.text(0.01, 0.97, title, fontsize=12, fontweight="bold", va="top")
    fig.text(0.01, 0.925, "100 = same share of chart space in Australia as in the US. Blue = over-indexes in AU, red = under.\n– = fewer than 3 titles (too few to score)",
             fontsize=8, color=MUTED, va="top")
    fig.savefig(CHARTS / filename, dpi=200, facecolor="white")
    plt.close(fig)


def chart_mix(mix):
    """Stacked horizontal bars: who fills Australian chart slots, per platform group."""
    order = ["News / sport / live (AU)", "AU", "US", "GB", "Other"]
    labels = {"News / sport / live (AU)": "News, sport, live (AU)", "AU": "Australian programs", "US": "US-made",
              "GB": "UK-made", "Other": "Other / unknown"}
    mix = mix.copy()
    mix["origin"] = mix.origin.replace("Unknown", "Other")
    grid = mix.groupby(["platform_group", "origin"]).share.sum().unstack().reindex(columns=order).fillna(0)
    grid = grid.iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 3.2))
    left = np.zeros(len(grid))
    for k, col in enumerate(order):
        vals = grid[col].values
        ax.barh(range(len(grid)), vals, left=left, color=CAT[k], edgecolor="white", linewidth=2, height=0.6, label=labels[col])
        for i, v in enumerate(vals):
            if v >= 0.06:
                ax.text(left[i] + v / 2, i, f"{v:.0%}", ha="center", va="center", color="white" if k in (0, 1) else TEXT, fontsize=9)
        left += vals
    ax.set_yticks(range(len(grid)), [GROUP_SHORT[g].replace("\n", " ") for g in grid.index])
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.tick_params(length=0)
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.legend(ncol=5, loc="upper left", bbox_to_anchor=(-0.25, -0.15), frameon=False, fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.text(0.01, 0.97, "Who fills Australia's top charts? Share of chart slots by content origin", fontsize=12, fontweight="bold", va="top")
    fig.savefig(CHARTS / "au_chart_mix.png", dpi=200, facecolor="white")
    plt.close(fig)


def chart_pickup(pickup):
    """Bar chart: share of each genre's US hits that also charted on Netflix AU."""
    d = pickup[(pickup.segment_type == "genre") & ~pickup.small_sample].sort_values("hit_rate")
    overall = d.travelled.sum() / d.us_hits.sum()
    fig, ax = plt.subplots(figsize=(7.5, 0.4 * len(d) + 1.4))
    ax.barh(d.segment, d.hit_rate, color=CAT[0], height=0.6)
    for i, (rate, n) in enumerate(zip(d.hit_rate, d.us_hits)):
        ax.text(rate + 0.01, i, f"{rate:.0%}  (n={n})", va="center", fontsize=9, color=MUTED,
                bbox=dict(facecolor="white", edgecolor="none", pad=1))
    ax.axvline(overall, color=MUTED, linestyle="--", linewidth=1, zorder=0)
    ax.text(overall + 0.01, -0.9, f"average {overall:.0%}", color=MUTED, fontsize=8, va="center")
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.tick_params(length=0)
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.text(0.01, 0.98, "Licensed US streaming hits (not Netflix originals): share that also charted on Netflix Australia",
             fontsize=12, fontweight="bold", va="top")
    fig.savefig(CHARTS / "netflix_pickup_by_genre.png", dpi=200, facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------- Excel
def add_table_sheet(wb, name, df, widths=None):
    """Write a DataFrame as an Excel Table with a frozen, bold header."""
    ws = wb.create_sheet(name)
    df = df.copy()
    for c in df.columns:  # Excel can't store pandas NA / numpy bools in some cases
        if df[c].dtype == bool:
            df[c] = df[c].map({True: "Yes", False: "No"})
    df = df.astype(object).where(df.notna(), None)
    ws.append(list(df.columns))
    for row in df.itertuples(index=False):
        ws.append(list(row))
    ref = f"A1:{get_column_letter(df.shape[1])}{df.shape[0] + 1}"
    table = Table(displayName=name.replace(" ", "_"), ref=ref)
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(table)
    ws.freeze_panes = "A2"
    for i, col in enumerate(df.columns, start=1):
        width = (widths or {}).get(col, min(max(len(str(col)), 10) + 2, 40))
        ws.column_dimensions[get_column_letter(i)].width = width
    for row in ws.iter_rows():
        for cell in row:
            cell.font = Font(name="Arial", size=10, bold=cell.row == 1, color="FFFFFF" if cell.row == 1 else "000000")
    return ws


def build_workbook():
    scores = pd.read_csv(P / "travel_score.csv")
    pickup = pd.read_csv(P / "netflix_pickup.csv")
    wb = Workbook()
    readme = wb.active
    readme.title = "README"
    lines = [
        ("Will It Travel? Which US shows succeed in Australia", True),
        ("Independent portfolio project. Not affiliated with or endorsed by NBCUniversal.", False),
        ("This product uses the TMDB API but is not endorsed or certified by TMDB.", False),
        ("", False),
        ("TABS", True),
        ("travel_score: genre/format x Australian platform group. travel_score = AU share / US share x 100 (live formula). 100 = same share of chart space in AU as in the US.", False),
        ("netflix_pickup: of each genre's LICENSED US hits (Netflix originals excluded), the share that also charted on Netflix Australia (hit_rate is a live formula).", False),
        ("au_chart_mix: share of Australian chart slots by content origin (AU, US, UK, news/sport).", False),
        ("sell_next: ranked NBCU titles to sell, best platform group and evidence (Output 4). renewals: licensed-but-not-charting watch-list.", False),
        ("title_travel: one row per US hit, with US and Australian rank percentiles per platform group.", False),
        ("matched_titles: one row per title family, all markets (Output 1).", False),
        ("charts_long: every weekly chart entry. Best tab for your own PivotTables.", False),
        ("uncertain_matches: title matches flagged for manual review.", False),
        ("", False),
        ("METHOD", True),
        ("We compare RANKS, not audiences: Nielsen measures minutes watched, OzTAM measures average viewers.", False),
        ("Every chart position becomes a rank percentile within its own chart (#1 = 1.0; #10 of 10 = 0.1; #30 of 30 = 0.033).", False),
        ("Platform groups: 1 Free-to-air = VOZ Total TV avg audience top 30; 2 BVOD = same programs re-ranked by BVOD avg audience; 3 Paid streaming = Netflix Top 10 Australia.", False),
        ("Window: Oct 2025 - Sep 2026. VOZ daily charts are turned into weekly charts using each program's best day of the week.", False),
        ("", False),
        ("SOURCES", True),
        ("US: Nielsen Streaming Top 10 (nielsen.com/data-center/top-ten) - 1 live week + 12 hand-entered weeks (sample, one+ per month).", False),
        ("US + AU: Netflix Top 10 (netflix.com/tudum/top10) - all 52 weeks.", False),
        ("AU: OzTAM VOZ Total TV Consolidated 7 Top 30 Programs (virtualoz.com.au). Source: OzTAM VOZ.", False),
        ("Metadata: TMDB API (genre, format, network, production companies).", False),
    ]
    for text, bold in lines:
        readme.append([text])
        readme.cell(readme.max_row, 1).font = Font(name="Arial", size=12 if bold else 10, bold=bold)
    readme.column_dimensions["A"].width = 140

    # travel_score with live formulas
    ts = scores[["segment_type", "segment", "platform_group", "au_share_of_us_content", "us_chart_share",
                 "travel_score", "au_titles", "small_sample", "example_titles"]].copy()
    ws = add_table_sheet(wb, "travel_score", ts, widths={"segment": 24, "platform_group": 30, "example_titles": 60})
    for r in range(2, len(ts) + 2):
        ws[f"F{r}"] = f'=IFERROR(ROUND(100*D{r}/E{r},0),"")'
        ws[f"F{r}"].font = Font(name="Arial", size=10)
        ws[f"D{r}"].number_format = ws[f"E{r}"].number_format = "0.0%"

    nf = pickup[["segment_type", "segment", "us_hits", "travelled", "hit_rate", "pickup_index",
                 "avg_rank_gap", "small_sample", "example_titles"]].copy()
    ws = add_table_sheet(wb, "netflix_pickup", nf, widths={"segment": 24, "example_titles": 60})
    for r in range(2, len(nf) + 2):
        ws[f"E{r}"] = f'=IFERROR(D{r}/C{r},"")'
        ws[f"E{r}"].number_format = "0.0%"
        ws[f"E{r}"].font = Font(name="Arial", size=10)

    mix = pd.read_csv(P / "au_chart_mix.csv")
    ws = add_table_sheet(wb, "au_chart_mix", mix, widths={"platform_group": 32, "origin": 26})
    for r in range(2, len(mix) + 2):  # share = slots / total slots in that platform group (live formula)
        ws[f"D{r}"] = f'=IFERROR(C{r}/SUMIFS($C$2:$C${len(mix)+1},$A$2:$A${len(mix)+1},A{r}),"")'
        ws[f"D{r}"].number_format = "0.0%"
        ws[f"D{r}"].font = Font(name="Arial", size=10)

    add_table_sheet(wb, "sell_next", pd.read_csv(P / "sell_next.csv"), widths={"tmdb_name": 32, "pitch_to": 44, "evidence": 90})
    add_table_sheet(wb, "renewals", pd.read_csv(P / "sell_next_renewals.csv"), widths={"tmdb_name": 32, "au_streaming_now": 50, "note": 60})
    add_table_sheet(wb, "title_travel", pd.read_csv(P / "title_travel.csv"), widths={"tmdb_name": 36, "networks": 30})
    add_table_sheet(wb, "matched_titles", pd.read_csv(P / "matched_titles.csv"), widths={"tmdb_name": 36, "chart_titles": 40})
    add_table_sheet(wb, "charts_long", pd.read_csv(P / "charts_long.csv"), widths={"title": 36, "platform_group": 30})
    add_table_sheet(wb, "uncertain_matches", pd.read_csv(P / "uncertain_matches.csv"), widths={"title": 36, "tmdb_name": 36})

    ws = wb.create_sheet("charts")
    row = 1
    for png in ["travel_score_genre.png", "travel_score_format.png", "au_chart_mix.png", "netflix_pickup_by_genre.png"]:
        img = XLImage(CHARTS / png)
        img.width, img.height = img.width * 0.35, img.height * 0.35
        ws.add_image(img, f"A{row}")
        row += int(img.height / 20) + 3
    wb.calculation.fullCalcOnLoad = True  # Excel computes the formula columns when the file opens
    wb.save(XLSX)
    print(f"Saved workbook -> {XLSX}  ({len(wb.sheetnames)} tabs: {', '.join(wb.sheetnames)})")


def main():
    CHARTS.mkdir(parents=True, exist_ok=True)
    scores = pd.read_csv(P / "travel_score.csv")
    heatmap(scores, "genre", "travel_score_genre.png", "Travel score by genre: where US content over-performs in Australia")
    heatmap(scores, "format", "travel_score_format.png", "Travel score by format")
    chart_mix(pd.read_csv(P / "au_chart_mix.csv"))
    chart_pickup(pd.read_csv(P / "netflix_pickup.csv"))
    print("Saved charts ->", ", ".join(p.name for p in sorted(CHARTS.glob("*.png"))))
    build_workbook()


if __name__ == "__main__":
    main()
