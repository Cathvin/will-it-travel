"""
Output 5: AI-written pitch briefs, one per Australian platform group (Claude API).

For each platform group we build a small "data pack" from our own outputs:
  - travel scores for that group (which genres/formats over- or under-index)
  - who fills that group's charts (AU / US / UK / news & sport)
  - the "what to sell next" titles best matched to that group, with evidence
  - renewal watch-list titles that fit that group better than their current home
Claude turns the data pack into a one-page pitch brief for a sales executive.
It is told to use ONLY the numbers in the data pack, so it can't invent figures.

Model: claude-opus-5-5. The API key is read from .env (ANTHROPIC_API_KEY), never printed.
Server-side refusal fallback is enabled (if a request is declined, the API retries it
on a fallback model automatically).

Output: outputs/briefs/<group>.md

Run:  .venv/bin/python src/write_briefs.py
"""
import json
from pathlib import Path

import anthropic
import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment

P = Path("data/processed")
OUT = Path("outputs/briefs")
MODEL = "claude-opus-5-5"

GROUPS = {
    "1 Free-to-air": ("free_to_air", "Free-to-air TV: Seven, Nine, Ten, ABC, SBS"),
    "2 BVOD": ("bvod", "Free streaming apps: 7plus, 9Now, 10 Play, ABC iview, SBS On Demand"),
    "3 Paid streaming (Netflix AU)": ("paid_streaming", "Paid streamers: Stan, Foxtel/BINGE, Netflix, Prime Video"),
}

SYSTEM = """You are a senior research analyst in a TV distribution team that licenses
NBCUniversal shows and films to Australian broadcasters and streamers.
Write a one-page pitch brief for a sales executive, in Markdown, Australian English.

Rules:
- Use ONLY facts and numbers from the data pack. Do not invent ratings, prices, deal terms or titles.
- If the data is thin for this platform group, say so plainly and recommend what to do anyway.
- Explain the travel score once in plain words: 100 = US content gets the same share of chart
  space in Australia as in the US; above 100 = it over-performs in Australia.
- Write for a busy executive: short sections, bullets, no jargon.

Structure:
# <Platform group>: pitch brief
**Bottom line:** one or two sentences.
## What this audience buys
## Titles to pitch (each: title, why it fits, the evidence)
## Renewal opportunities (if any)
## How to pitch it (positioning / slot / packaging ideas grounded in the data)
## Caveats (data limits, in one short list)"""


def data_pack(group):
    """Collect everything Claude needs for one platform group as a JSON-friendly dict."""
    scores = pd.read_csv(P / "travel_score.csv")
    s = scores[(scores.platform_group == group) & ~scores.small_sample]
    mix = pd.read_csv(P / "au_chart_mix.csv")
    sell = pd.read_csv(P / "sell_next.csv")
    ren = pd.read_csv(P / "sell_next_renewals.csv")
    pickup = pd.read_csv(P / "netflix_pickup.csv")

    pack = {
        "platform_group": GROUPS[group][1],
        "data_window": "Oct 2025 - Sep 2026. AU: OzTAM VOZ daily Top 30 (free-to-air & BVOD), Netflix Top 10 Australia. "
                       "US: Nielsen Streaming Top 10 (13-week sample) and Netflix Top 10 US.",
        "travel_scores_genre": s[s.segment_type == "genre"][["segment", "travel_score", "au_titles", "example_titles"]]
                                .sort_values("travel_score", ascending=False).to_dict("records"),
        "travel_scores_format": s[s.segment_type == "format"][["segment", "travel_score", "au_titles", "example_titles"]]
                                 .sort_values("travel_score", ascending=False).to_dict("records"),
        "chart_slot_mix": mix[mix.platform_group == group][["origin", "share"]].to_dict("records"),
        "titles_to_pitch": sell[sell.best_group == group][["rank", "tier", "tmdb_name", "year", "format", "sales_genre",
                                                          "opportunity_score", "evidence"]].head(8).to_dict("records"),
        "renewal_opportunities": ren[ren.best_group == group][["tmdb_name", "year", "format", "au_streaming_now", "note"]]
                                  .head(6).to_dict("records"),
        "notes": [
            "Groups 1 and 2 scores rest on a small number of US titles (roughly 10) - treat as direction, not precision.",
            "Stan, BINGE and Prime Video publish no charts, so group 3 uses Netflix Top 10 Australia as the proxy.",
            "Peacock originals are excluded (covered by Stan's NBCUniversal output deal).",
        ],
    }
    if group.startswith("3"):
        pack["netflix_licensed_title_pickup"] = {
            "headline": "91% of Netflix originals that hit in the US also chart in Australia, vs 28% of licensed US hits.",
            "by_genre": pickup[(pickup.segment_type == "genre") & ~pickup.small_sample][["segment", "us_hits", "hit_rate"]].to_dict("records"),
        }
    return pack


def write_brief(group):
    pack = data_pack(group)
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM,
        messages=[{"role": "user", "content": "Data pack:\n```json\n" + json.dumps(pack, indent=1, default=str) + "\n```"}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Request for {group} was declined: {response.stop_details}")
    text = "".join(b.text for b in response.content if b.type == "text")
    footer = ("\n\n---\n*AI-drafted with Claude from this project's data "
              "(OzTAM VOZ, Netflix Top 10, Nielsen, TMDB/JustWatch). Check before sending. "
              "Independent project, not affiliated with NBCUniversal.*\n")
    path = OUT / f"{GROUPS[group][0]}.md"
    path.write_text(text.strip() + footer, encoding="utf-8")
    print(f"Saved {path}  ({response.usage.output_tokens} output tokens, served by {response.model})")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for group in GROUPS:
        try:
            write_brief(group)
        except anthropic.RateLimitError:
            print(f"Rate limited on {group} - re-run later")
        except anthropic.APIStatusError as e:
            print(f"API error on {group}: {e.status_code} {e.message}")
        except anthropic.APIConnectionError:
            print(f"Network error on {group}")


if __name__ == "__main__":
    main()
