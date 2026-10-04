"""
Output 6: 6-slide executive PowerPoint (python-pptx) that leads with the recommendation.

  1. The recommendation (dark)
  2. Free TV buys US crime procedurals - and almost nothing else
  3. On paid streaming, a US hit is not enough: licensed titles rarely travel
  4. What travels on paid streaming (travel score by genre)
  5. What to sell next (ranked list + renewal watch-list)
  6. Next steps and caveats (dark)

Every number is read from data/processed/*.csv, so re-running the pipeline updates the deck.
Charts are native PowerPoint charts (editable in PowerPoint), not pictures.

Output: outputs/will_it_travel_exec.pptx

Run:  .venv/bin/python src/build_deck.py
"""
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

P = Path("data/processed")
OUT = Path("outputs/will_it_travel_exec.pptx")

# Palette: deep navy (dominant), coral accent, cool greys
NAVY = RGBColor(0x1B, 0x2A, 0x41)
CORAL = RGBColor(0xE4, 0x57, 0x2E)
SLATE = RGBColor(0x5B, 0x6B, 0x82)
MIST = RGBColor(0xEE, 0xF1, 0xF5)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
INK = RGBColor(0x1A, 0x1A, 0x1A)
HEAD, BODY = "Cambria", "Calibri"
FOOTER = "Independent portfolio project - not affiliated with NBCUniversal. Sources: OzTAM VOZ, Netflix Top 10, Nielsen, TMDB/JustWatch."


# ---------------------------------------------------------------- helpers
def text(slide, x, y, w, h, content, size=16, bold=False, color=INK, font=BODY, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    """Add a text box. `content` is a string or a list of (text, size, bold, color) paragraphs."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0)
    paras = content if isinstance(content, list) else [(content, size, bold, color)]
    for i, (t, s, b, c) in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(6)
        run = p.add_run()
        run.text = t
        run.font.size, run.font.bold, run.font.color.rgb, run.font.name = Pt(s), b, c, font
    return box


def card(slide, x, y, w, h, fill=MIST):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.adjustments[0] = 0.08
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


def badge(slide, x, y, label, fill=CORAL):
    """Numbered circle - the deck's repeated visual motif."""
    c = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(0.5), Inches(0.5))
    c.fill.solid()
    c.fill.fore_color.rgb = fill
    c.line.fill.background()
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(16), True, WHITE, BODY
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE


def base_slide(prs, title, dark=False):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = NAVY if dark else WHITE
    text(slide, 0.6, 0.35, 12.1, 1.1, title, size=28 if not dark else 30, bold=True,
         color=WHITE if dark else NAVY, font=HEAD)
    text(slide, 0.6, 7.0, 12.1, 0.3, FOOTER, size=10, color=RGBColor(0xB8, 0xC2, 0xD0) if dark else SLATE)
    return slide


def bar_chart(slide, x, y, w, h, categories, values, title, number_format='0', highlight=None, ref_line=None):
    data = CategoryChartData()
    data.categories = categories
    data.add_series("Score", values)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), data)
    ch = gf.chart
    ch.has_legend = False
    ch.has_title = True
    ch.chart_title.text_frame.text = title
    tp = ch.chart_title.text_frame.paragraphs[0]
    tp.runs[0].font.size, tp.runs[0].font.bold, tp.runs[0].font.color.rgb, tp.runs[0].font.name = Pt(14), True, NAVY, BODY
    plot = ch.plots[0]
    plot.gap_width = 60
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format, dl.number_format_is_linked = number_format, False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size, dl.font.color.rgb, dl.font.name = Pt(12), INK, BODY
    ser = plot.series[0]
    for i, cat in enumerate(categories):
        pt = ser.points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = CORAL if (highlight and highlight(cat, values[i])) else SLATE
    ca, va = ch.category_axis, ch.value_axis
    ca.tick_labels.font.size, ca.tick_labels.font.color.rgb, ca.tick_labels.font.name = Pt(12), INK, BODY
    ca.format.line.fill.background()
    ca.reverse_order = True  # first category at the top
    va.visible = False
    va.has_major_gridlines = False
    return ch


# ---------------------------------------------------------------- data
def load():
    d = {}
    d["scores"] = pd.read_csv(P / "travel_score.csv")
    d["mix"] = pd.read_csv(P / "au_chart_mix.csv")
    d["pickup"] = pd.read_csv(P / "netflix_pickup.csv")
    d["sell"] = pd.read_csv(P / "sell_next.csv")
    d["ren"] = pd.read_csv(P / "sell_next_renewals.csv")
    tt = pd.read_csv(P / "title_travel.csv")
    d["orig_rate"] = tt[tt.is_netflix_original].au_svod_charted.mean()
    d["lic_rate"] = tt[~tt.is_netflix_original].au_svod_charted.mean()
    nb = tt[tt.is_nbcu == True]
    d["nbcu_hits"], d["nbcu_au"] = len(nb), int((nb.au_groups_charted > 0).sum())
    return d


def score(d, seg_type, seg, group):
    s = d["scores"]
    r = s[(s.segment_type == seg_type) & (s.segment == seg) & (s.platform_group == group)]
    return int(r.travel_score.iloc[0]) if len(r) else 0


def share(d, group, origin):
    m = d["mix"]
    r = m[(m.platform_group == group) & (m.origin == origin)]
    return float(r.share.iloc[0]) if len(r) else 0.0


# ---------------------------------------------------------------- slides
def slide1(prs, d):
    s = base_slide(prs, "Recommendation: procedurals to free TV, films and docs to paid streamers", dark=True)
    recs = [
        ("1", "Free TV: lead with crime procedurals",
         f"US scripted series score {score(d, 'format', 'Scripted series', '1 Free-to-air')} on free-to-air; US films score "
         f"{score(d, 'format', 'Film', '1 Free-to-air')}. Re-pitch Law & Order, La Brea and All Her Fault to the networks at renewal."),
        ("2", "Paid streamers: film, family, true crime",
         f"Documentary ({score(d, 'format', 'Documentary', '3 Paid streaming (Netflix AU)')}) and animated film "
         f"({score(d, 'format', 'Animated film', '3 Paid streaming (Netflix AU)')}) over-index. Start with The Super Mario Galaxy Movie and Homicide Squad New Orleans."),
        ("3", "Back licensed titles with marketing",
         f"Only {d['lic_rate']:.0%} of licensed US hits chart in Australia vs {d['orig_rate']:.0%} of Netflix originals. "
         f"{len(d['ren'])} NBCU titles are licensed here but never chart."),
    ]
    for i, (n, head, body) in enumerate(recs):
        x = 0.6 + i * 4.1
        card(s, x, 2.0, 3.8, 4.6, fill=RGBColor(0x26, 0x3A, 0x57))
        badge(s, x + 0.3, 2.3, n)
        text(s, x + 0.3, 3.0, 3.2, 1.0, head, size=20, bold=True, color=WHITE, font=HEAD)
        text(s, x + 0.3, 4.1, 3.2, 2.4, body, size=15, color=RGBColor(0xDD, 0xE3, 0xEA))
    s.notes_slide.notes_text_frame.text = (
        "Lead with the answer. Three moves: procedurals to free TV, films/docs/family to paid streamers, "
        "and marketing support for titles already licensed. Data: Oct 2025 - Sep 2026, rankings only (never raw audiences).")


def slide2(prs, d):
    s = base_slide(prs, "Free TV buys US crime procedurals, and almost nothing else")
    fta, bvod = share(d, "1 Free-to-air", "US"), share(d, "2 BVOD", "US")
    news = share(d, "1 Free-to-air", "News / sport / live (AU)")
    stats = [(f"{fta:.1%}", "of free-to-air Top 30 slots go to US-made content"),
             (f"{bvod:.1%}", "on the free streaming apps, twice the broadcast share"),
             (f"{news:.0%}", "of free-to-air slots are news, sport and live events")]
    for i, (big, label) in enumerate(stats):
        y = 1.6 + i * 1.75
        text(s, 0.6, y, 4.2, 0.9, big, size=48, bold=True, color=CORAL, font=HEAD)
        text(s, 0.6, y + 0.9, 4.2, 0.7, label, size=14, color=SLATE)
    fmts = ["Scripted series", "Film"]
    cats = [f"{f} - free-to-air" for f in fmts] + [f"{f} - free apps" for f in fmts]
    vals = [score(d, "format", f, "1 Free-to-air") for f in fmts] + [score(d, "format", f, "2 BVOD") for f in fmts]
    bar_chart(s, 5.3, 1.5, 7.4, 3.6, cats, vals, "Travel score by format (100 = same share of chart space as in the US)",
              highlight=lambda c, v: v >= 100)
    card(s, 5.3, 5.35, 7.4, 1.4)
    text(s, 5.6, 5.5, 6.9, 1.2, [("What charts:", 14, True, NAVY),
                                 ("The Rookie, 9-1-1, Murder in a Small Town, The Hunting Wives - all US crime/procedural series on Seven and Ten.", 14, False, INK)])
    s.notes_slide.notes_text_frame.text = (
        "Australian free TV is mostly local: news, sport and Australian programs take ~90% of top-30 slots. "
        "When US content gets in, it is scripted crime series. Films almost never chart. Small sample (~10 US titles) - direction, not precision.")


def slide3(prs, d):
    s = base_slide(prs, "On paid streaming, a US hit is not enough: licensed titles rarely travel")
    for i, (big, label, col) in enumerate([(f"{d['orig_rate']:.0%}", "of Netflix originals that hit in the US also chart in Australia", SLATE),
                                           (f"{d['lic_rate']:.0%}", "of LICENSED US hits do: the titles a distributor actually sells", CORAL)]):
        card(s, 0.6 + i * 3.0, 1.6, 2.8, 2.6)
        text(s, 0.8 + i * 3.0, 1.8, 2.4, 1.0, big, size=54, bold=True, color=col, font=HEAD)
        text(s, 0.8 + i * 3.0, 2.9, 2.4, 1.2, label, size=14, color=INK)
    text(s, 0.6, 4.5, 5.8, 2.2, [
        ("Why it matters", 16, True, NAVY),
        ("Netflix originals launch worldwide on the same day. Licensed shows need a local deal, a local home and local promotion to break through.", 14, False, INK),
        (f"NBCU: {d['nbcu_au']} of {d['nbcu_hits']} US chart hits also charted in Australia.", 14, True, CORAL)])
    pk = d["pickup"]
    pk = pk[(pk.segment_type == "genre") & ~pk.small_sample & (pk.us_hits >= 10)].sort_values("hit_rate", ascending=False)
    bar_chart(s, 6.8, 1.5, 5.9, 5.2, pk.segment.tolist(), pk.hit_rate.round(3).tolist(),
              "Licensed US hits that also charted on Netflix AU, by genre", number_format="0%",
              highlight=lambda c, v: v >= d["lic_rate"])
    s.notes_slide.notes_text_frame.text = (
        "Same-title lens on Netflix Top 10 US vs Australia (52 weeks each, same metric). Netflix originals excluded from the genre chart "
        "because they launch globally. Documentary is the standout for licensed titles.")


def slide4(prs, d):
    s = base_slide(prs, "Paid streamers over-index on horror, comedy, documentary and family; drama and reality lag")
    sc = d["scores"]
    g = sc[(sc.segment_type == "genre") & (sc.platform_group == "3 Paid streaming (Netflix AU)") & ~sc.small_sample]
    g = g.sort_values("travel_score", ascending=False)
    bar_chart(s, 0.6, 1.5, 7.6, 5.3, g.segment.tolist(), g.travel_score.astype(int).tolist(),
              "Travel score by genre, paid streaming (100 = same share as in the US)", highlight=lambda c, v: v >= 110)
    card(s, 8.6, 1.6, 4.1, 5.1)
    text(s, 8.9, 1.8, 3.6, 4.8, [
        ("How to read it", 16, True, NAVY),
        ("Each chart position is turned into a rank percentile, so Nielsen minutes and Australian viewer counts are never compared directly.", 14, False, INK),
        ("A score of 134 means that genre wins 34% more of Australia's US-content chart space than its share of US charts.", 14, False, INK),
        ("Pitch: horror, comedy, documentary and family films. Sell reality as a format to remake locally instead.", 14, True, CORAL)])
    s.notes_slide.notes_text_frame.text = (
        "Australians watch US horror, comedy and docs on streaming more than the US weight would predict. "
        "US reality under-indexes because local versions (MAFS, The Block, Love Island Australia) fill that need.")


def slide5(prs, d):
    s = base_slide(prs, "What to sell next: NBCU titles proven in the US with no Australian home")
    sell = d["sell"]
    top = pd.concat([sell[sell.tier.str.startswith("A")], sell[sell.tier.str.startswith("B")].head(4)])
    rows, cols = len(top) + 1, 4
    tbl = s.shapes.add_table(rows, cols, Inches(0.6), Inches(1.5), Inches(8.0), Inches(0.42 * rows)).table
    widths = [3.4, 1.7, 1.9, 1.0]
    heads = ["Title", "Evidence", "Pitch to", "Score"]
    group_short = {"1 Free-to-air": "Free-to-air", "2 BVOD": "Free apps", "3 Paid streaming (Netflix AU)": "Paid streamers"}
    for j, (wd, hd) in enumerate(zip(widths, heads)):
        tbl.columns[j].width = Inches(wd)
        c = tbl.cell(0, j)
        c.text = hd
        c.fill.solid()
        c.fill.fore_color.rgb = NAVY
    for i, r in enumerate(top.itertuples(), start=1):
        vals = [f"{r.tmdb_name} ({int(r.year)})", "US chart hit" if r.tier.startswith("A") else "US signal (TMDB)",
                group_short[r.best_group], f"{r.opportunity_score:.0f}"]
        for j, v in enumerate(vals):
            c = tbl.cell(i, j)
            c.text = v
            c.fill.solid()
            c.fill.fore_color.rgb = MIST if i % 2 else WHITE
    for i in range(rows):
        for j in range(cols):
            for p in tbl.cell(i, j).text_frame.paragraphs:
                for run in p.runs:
                    run.font.size, run.font.name = Pt(14 if i else 14), BODY
                    run.font.bold = i == 0
                    run.font.color.rgb = WHITE if i == 0 else INK
    ren = d["ren"]
    rp = ren[ren.best_group != ren.current_group].tmdb_name.tolist()
    card(s, 9.0, 1.5, 3.7, 5.2)
    text(s, 9.3, 1.7, 3.2, 4.9, [
        ("Renewal watch-list", 16, True, NAVY),
        (f"{len(ren)} NBCU titles are licensed in Australia but never chart.", 14, False, INK),
        ("Re-pitch to free-to-air at renewal:", 14, True, CORAL),
        (", ".join(rp) + ".", 14, False, INK),
        ("Excluded: Peacock originals (Stan output deal) and other streamers' originals.", 12, False, SLATE)])
    s.notes_slide.notes_text_frame.text = (
        "Tier A = charted in US Top 10s, never in Australia, no Australian streaming home (JustWatch via TMDB). "
        "Tier B = NBCU titles 2022-2025 with strong US audience signal and no Australian home; weaker evidence. "
        "Full list with evidence in data/processed/sell_next.csv and the briefs in outputs/briefs/.")


def slide6(prs, d):
    s = base_slide(prs, "Next steps", dark=True)
    steps = [("1", "Open procedural conversations with Seven and Ten", "Package Law & Order with newer crime series; use The Rookie and 9-1-1 as proof points."),
             ("2", "Take the film and family slate to Stan and BINGE", "Lead with The Super Mario Galaxy Movie, then Migration, Fast X and Renfield."),
             ("3", "Add marketing commitments to licence renewals", "Licensed titles chart far less often than originals: make promotion part of the deal."),
             ("4", "Close the data gaps", "Add full Nielsen history and subscriber data for Stan and BINGE to test these patterns.")]
    for i, (n, head, body) in enumerate(steps):
        y = 1.6 + i * 1.2
        badge(s, 0.6, y + 0.05, n)
        text(s, 1.3, y, 6.6, 0.5, head, size=18, bold=True, color=WHITE, font=HEAD)
        text(s, 1.3, y + 0.5, 6.6, 0.6, body, size=14, color=RGBColor(0xDD, 0xE3, 0xEA))
    card(s, 8.4, 1.6, 4.3, 5.0, fill=RGBColor(0x26, 0x3A, 0x57))
    text(s, 8.7, 1.8, 3.8, 4.7, [
        ("Caveats", 16, True, WHITE),
        ("Free TV scores rest on ~10 US titles: direction, not precision.", 14, False, RGBColor(0xDD, 0xE3, 0xEA)),
        ("Stan, BINGE and Prime publish no charts; Netflix Australia is the proxy.", 14, False, RGBColor(0xDD, 0xE3, 0xEA)),
        ("Nielsen is a 13-week sample; Netflix covers all 52 weeks.", 14, False, RGBColor(0xDD, 0xE3, 0xEA)),
        ("Rights and availability from public data; confirm with contracts.", 14, False, RGBColor(0xDD, 0xE3, 0xEA))])
    s.notes_slide.notes_text_frame.text = "Close on actions and be upfront about the data limits."


def main():
    d = load()
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    for build in (slide1, slide2, slide3, slide4, slide5, slide6):
        build(prs, d)
    prs.save(OUT)
    print(f"Saved {OUT} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
