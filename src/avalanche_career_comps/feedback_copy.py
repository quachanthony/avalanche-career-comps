"""Write clear article explanations from the actual revised comparisons."""

from __future__ import annotations

import csv
from html import escape

from . import inputs


def explanations(reports):
    """Keep every quoted match, weight and ratio tied to the selected model."""
    roster = reports["roster"]
    with_games = reports["method_revision"]["career_games_weighted"]
    rows = {(r["window"], r["player_id"]): r for r in roster["rows"]}
    mac = rows["whole_career", 8477492]
    age_mac = rows["age_aligned", 8477492]
    makar = reports["makar"]["isolation"]
    cale = makar["rows"][0]
    forsberg = reports["forsberg"]["matches"]
    skater = rows["whole_career", 8480069]
    labels = {
        "goals_per_82": "goals",
        "assists_per_82": "assists",
        "shots_per_82": "shots",
        "pim_per_82": "penalty minutes",
        "adjusted_pp_points_per_82": "power-play points",
        "log_games": "log-transformed career games",
        "pk_minutes_per_game": "PK minutes",
    }
    weights = "; ".join(f"{labels[k]} {100 * v:.1f}%" for k, v in skater["weights"].items())
    method = (
        "I compared full NHL regular-season careers through 2025–26 using goals, assists, "
        "shots, penalty minutes and power-play points per 82 games. Scoring and shot rates "
        "are adjusted for era. I put the stats on comparable scales and combine their "
        "weighted differences into one gap; the smallest gap identifies the closest "
        "eligible former Av. "
        + (
            "Career length also enters the score as log(1 + games). "
            if with_games
            else "Career games are shown as sample-size context and do not affect the match. "
        )
        + "Missing PK minutes never remove an otherwise eligible alumnus: when coverage "
        "is incomplete anywhere in the comparison pool, I leave that stat out."
    )
    if not with_games:
        fs = (
            f"{forsberg[0]['name']} and {forsberg[1]['name']} are almost tied for Forsberg's "
            f"closest statistical comparison: their gaps are {forsberg[0]['distance']:.3f} "
            f"and {forsberg[1]['distance']:.3f}, respectively. {forsberg[2]['name']} is third. "
            "The tiny lead is not evidence of a meaningful difference in playing style. "
            "With career length removed from the score, Rantanen's similar number of "
            "games no longer helps his match. Forsberg's adjusted assist rate still "
            "stands out against all three."
        )
    else:
        fs = (
            f"Forsberg's closest statistical comparison is {forsberg[0]['name']}, followed by "
            f"{forsberg[1]['name']} and {forsberg[2]['name']}. This model includes career length, "
            "so similar games played help a match even when one career was shortened by "
            "injuries and the other remains unfinished. The production-only sensitivity "
            "puts Sakic and Rantanen almost level."
        )
    return {
        "title": "How Today’s Avs Stack Up Against Colorado’s Past",
        "subtitle": "Comparing today’s Avalanche with the franchise’s past, one statistical profile at a time.",
        "opening": f"Nathan MacKinnon's closest statistical comparison is {mac['matches'][0]['name']}. "
        "Their era-adjusted goal and assist rates are close, although MacKinnon "
        "takes more shots. It is a comparison of observed production, not a "
        "prediction that their careers will finish in the same place.",
        "short_method": method,
        "eligibility": "Skaters qualify after 82 Colorado regular-season appearances; goalies need 50. "
        "Forwards, defensemen and goalies are matched separately. Once a player "
        "qualifies, his NHL record across every team counts. The roster is a "
        "November 10, 2026 snapshot; the statistics stop at the completed 2025–26 season.",
        "forwards": "MacKinnon–Sakic and Kadri–Smyth are examples of similar production profiles. "
        "Each current player is matched separately, so the same alumnus can "
        "appear more than once. A statistical match does not capture every "
        "part of a player's style or importance to a team.",
        "defensemen": "The revised search keeps all eligible historical defensemen available. "
        "Makar now matches Bourque, and Burns matches Ozolinsh. The earlier "
        "Barrie comparisons depended partly on a PK coverage restriction, "
        "so they should not be presented as a finding about every offensive defenseman.",
        "goalies": "Goalies use four equally weighted measures: save percentage above league, "
        "era-adjusted shots faced per appearance, and quality-start and shutout "
        "rates relative to each season's league. The last two measure excess "
        "outcomes per 100 starts. Games and starts show sample size and do not "
        "carry similarity weight. These are statistical profiles, not WAR or "
        "a measure separating the goalie from his team's defense.",
        "cale": f"{cale['nearest_name']} is Makar's nearest comparison in both the roster chart "
        f"and the five-player overlay, using the same stats and all {makar['reference_count']} "
        f"eligible alumni. Their gap is {cale['distance']:.3f}. The median of the "
        f"alumni's own nearest-match gaps is {makar['typical_gap']:.3f}. Makar's "
        f"nearest-match gap is therefore {cale['ratio_to_median']:.1f} times that median. "
        "This measures distance from an available statistical comparison, not "
        "difficulty, overall quality or how many times better he is. Even after "
        "adjusting for era, Makar has higher goal, assist and PP-point rates than Bourque.",
        "forsberg": fs,
        "same_age": f"As a separate check, I cut the former players' records off at each current "
        f"Av's season-age. Through age {age_mac['age']}, MacKinnon's closest match "
        f"is still {age_mac['matches'][0]['name']}, with a gap of "
        f"{age_mac['matches'][0]['distance']:.2f}. This compares observed careers "
        "at a similar age; it does not project anyone's future or estimate an aging curve. "
        "The full same-age set is supplied separately.",
        "gap": "Gap is the weighted statistical distance between the two profiles. Zero "
        "would mean identical values on the matching stats; lower is closer. "
        "It is not a percentage or a calibrated quality grade. Each comparison "
        "uses its own eligible pool and spreads, so gaps across different pools "
        "are not a universal ranking of match quality.",
        "legend": "Burgundy always identifies the target in that chart; blue identifies "
        "the named comparison. In the Forsberg charts, Forsberg is the target. "
        "Closer spoke markers mean more similar values; shaded overlap is not "
        "the similarity score. The Cale overlay names all five colors in its legend.",
        "weights": weights + ". These are declared descriptive choices, not weights learned "
        "from a prediction target. The prior model is retained as a labeled baseline.",
        "pk": "NHL time-on-ice records begin in 1997–98, and some later records are incomplete "
        "or fail consistency checks. Missing minutes are never treated as zero. "
        "PK could receive 10% only if the target averaged at least one minute per "
        "game and every eligible comparison had complete audited minutes. No "
        "full-career skater chart in this revised article meets that full-pool rule, "
        "so none uses PK in its score.",
        "hughes": "T.J. Hughes appears on the roster snapshot but has no NHL regular-season "
        "games through the completed 2025–26 cutoff. He cannot meet the 50-game "
        "minimum for a target profile, so no comparison is assigned.",
        "pp_reference": "I use reference league rates of 3 goals, 5 assists and 30 shots per "
        "team-game. PP points use the actual 2025–26 league environment, "
        "about 1.77 per team-game. That reference sets display units: "
        "choosing another positive common reference would not change "
        "the standardized matches. Calculations retain full precision.",
        "glossary": "G/82, A/82, S/82 and PP/82 are era-adjusted goals, assists, shots and "
        "power-play points per 82 games. PIM/82 is unadjusted penalty minutes "
        "per 82. GP means NHL regular-season games. SV+ is save percentage "
        "above league, in percentage points. SA/G is adjusted shots faced "
        "per appearance. QS+ and SO+ are excess quality starts and shutouts "
        "per 100 starts relative to each season's league. The NHL's reported "
        "quality-start counts are used, rather than another provider's definition.",
        "source": "Statistics come from official NHL player pages and NHL Stats reports. "
        "The frozen inputs, equations, complete weights and reproduction code "
        "for this proposed revision are at https://github.com/quachanthony/avalanche-career-comps/tree/codex/article-feedback . "
        "Official TOI coverage: https://media.nhl.com/site/vasset/public/attachments/2023/06/17229/AllRookieTeam.pdf .",
        "closing": "The data and code to reproduce these comparisons are available on GitHub. "
        "I’ll keep using this space to learn in public and explore Avs hockey with data. "
        "Anyone stick out to you? Which comparison would you like to see next?",
    }


def write(reports, out):
    """Supply copy-ready prose, a paired-image reading preview and an explicit change checklist."""
    text = explanations(reports)
    inputs.write_json(out / "explanations.json", text)
    blocks = [
        ("Title", "title"),
        ("Subtitle", "subtitle"),
        ("Open with the payoff", "opening"),
        ("One short method paragraph", "short_method"),
        ("Eligibility", "eligibility"),
        ("Forwards", "forwards"),
        ("Defensemen", "defensemen"),
        ("Goalies", "goalies"),
        ("All Hail Cale", "cale"),
        ("Loosely, the Moose", "forsberg"),
        ("Same-age check", "same_age"),
        ("Method notes: reading the gap", "gap"),
        ("Method notes: colors", "legend"),
        ("Method notes: weights", "weights"),
        ("Method notes: PK coverage", "pk"),
        ("Method notes: Hughes", "hughes"),
        ("Method notes: PP reference", "pp_reference"),
        ("Method notes: glossary", "glossary"),
        ("Sources", "source"),
        ("Suggested closing", "closing"),
    ]
    (out / "article-explanations.txt").write_text(
        "\n\n".join(title + "\n" + text[key] for title, key in blocks) + "\n", encoding="utf-8"
    )
    if not (out / "alt-text.csv").exists():
        return
    with (out / "alt-text.csv").open(encoding="utf-8") as handle:
        images = list(csv.DictReader(handle))

    def image(row):
        return f'<figure><img src="{row["file"]}" alt="{escape(row["alt_text"], quote=True)}"></figure>'

    def para(key):
        return "<p>" + escape(text[key]) + "</p>"

    body = f'<h1>{escape(text["title"])}</h1><p class="subtitle">{escape(text["subtitle"])}</p>'
    body += para("opening") + image(next(r for r in images if r["section"] == "Opener"))
    body += para("short_method") + para("eligibility")
    for section, key in [
        ("Forwards", "forwards"),
        ("Defensemen", "defensemen"),
        ("Goalies", "goalies"),
    ]:
        body += f"<h2>{section}</h2>" + para(key)
        body += "".join(
            image(r)
            for r in images
            if r["window"] == "whole_career"
            and r["section"] == section
            and "/overview/" in r["file"]
        )
    body += (
        "<h2>All Hail Cale</h2>"
        + para("cale")
        + image(next(r for r in images if r["section"] == "Cale"))
    )
    body += (
        "<h2>Loosely, the Moose</h2>"
        + para("forsberg")
        + image(next(r for r in images if r["section"] == "Forsberg overview"))
    )
    body += "<h2>A same-age check</h2>" + para("same_age")
    body += image(
        next(
            r for r in images if r["window"] == "age_aligned" and r["target"] == "Nathan MacKinnon"
        )
    )
    body += '<p><a href="age-adjusted/index.html">Complete same-age supplement</a></p>'
    body += "<h2>Method notes</h2>" + "".join(
        para(k)
        for k in ["gap", "legend", "weights", "pk", "hughes", "pp_reference", "glossary", "source"]
    )
    body += "<h2>Your turn</h2>" + para("closing")
    (out / "article-preview.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Revised article reading order</title><style>body{max-width:760px;margin:30px auto;padding:0 16px;"
        "font:18px/1.65 Georgia,serif;color:#182d3c}h1,h2{font-family:system-ui;line-height:1.2}img{width:100%;display:block}"
        "figure{margin:24px 0 36px}.subtitle{color:#587080;font-size:21px}a{color:#236192}</style>"
        + body
        + "</html>",
        encoding="utf-8",
    )
