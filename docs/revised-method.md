# Current rate-profile method

This is the primary article model, confirmed on November 12, 2026. Full observed
careers lead the article; career games are displayed as sample-size context and carry
no similarity weight. The original data and original six-stat model remain preserved
as a reproducible baseline.
The baseline is available at commit `2033214` of the public repository.

## Primary choices

1. **Preserve the whole eligible pool.** A missing PK record removes that feature from
   a comparison, never an otherwise eligible alumnus. PK could enter at 10% only when
   the target averages at least one minute per game and the target and every eligible
   candidate have complete, agreeing minute records. No full-career skater chart in
   this dataset meets that complete-pool rule.
2. **Treat career games as exposure context.** Full observed careers remain primary,
   but GP no longer affects the rate-profile score. The five matching features are
   era-adjusted goals, assists, shots and PP points per 82 games, plus unadjusted PIM/82.
   GP remains visible beside every comparison. The same-age supplement is separate.
3. **Keep the goalie method unchanged.** SV+, adjusted SA/G, QS+ and SO+ still each
   receive 25%. Appearances and starts are context, not matching features.
4. **Explain coverage precisely.** Official NHL time-on-ice records begin in 1997–98;
   later records can also be incomplete or disagree. Hughes has no NHL regular-season
   games through the completed 2025–26 cutoff. Missing values never become zero.

## Exact revised skater weights

| Feature | Exact share | Displayed weight |
| --- | --- | --- |
| Goals/82 | 1/4 | 25.0% |
| Assists/82 | 1/4 | 25.0% |
| Shots/82 | 3/14 | 21.4% |
| PIM/82 | 1/7 | 14.3% |
| PP points/82 | 1/7 | 14.3% |

The relative proportions of the retained features are unchanged. Removing log career
GP causes renormalization; weights were not searched to obtain particular matches.
These are declared descriptive choices, not empirically fitted or validated weights.
If PK were usable, the five production shares would be multiplied by 0.9 and PK would
receive exactly 0.1. The era adjustment, population-SD scaling and weighted Euclidean
formula are otherwise unchanged from [the baseline equations](methods.md).

## Keep the controlled comparisons separate

| Result | Original restricted baseline | Preserve pool, retain career GP | Preserve pool, omit career GP |
| --- | --- | --- | --- |
| Makar's nearest alumnus | Barrie | Bourque | Bourque |
| Burns's nearest alumnus | Barrie | Ozolinsh | Ozolinsh |
| Makar's shared-stat nearest-gap ratio | 4.61× in the separate broader check | 4.61× | 5.13× |
| Forsberg's first two | Rantanen, Sakic | Rantanen, Sakic | Sakic, Rantanen; nearly tied |

The revised rate-only model changes 15 full-career and 12 same-age closest matches;
all four goalie-window results remain identical. This is a substantive method revision,
not a claim that the old numbers changed because new source data arrived.
`career-length-sensitivity.csv` separates the PK policy change from career length.

Under the original PK restriction, both Makar and Burns went from 45 eligible defensemen
to 29 ranked candidates. The 16 excluded players included Bourque, Ozolinsh, Rob Blake
and Adam Foote. The revised search keeps all 45. Their names are no longer dropped
because a career contains missing or disagreeing minute records.

For Makar, all 45 historical defensemen participate in both the roster search and the
special overlay. His gap to Bourque is **1.401108**. The median historical nearest-match
gap is **0.272958**, giving **5.133045×**. The means, spreads and weights are fitted to
those 45 alumni and held fixed for all pairs. Self-matches are excluded. Adding Makar
to the nearest-neighbor search changes Bourque's own nearest match to Makar; this is
recorded in the report, rather than retaining the original assumption that no historical
neighbor changes. The median happens to remain unchanged by that addition.

The ratio measures a distance relative to a median, not difficulty, quality, a probability,
or NHL-wide uniqueness. Do not reuse 4.6× for this five-stat model.

Forsberg's gaps to Sakic and Rantanen are **1.139993** and **1.143946**. Their ordering is
numerical; the tiny difference should not be treated as a meaningful separation in style
or ability. The charts show three decimals for this near-tie and the prose explicitly
calls it nearly tied. MacKinnon remains third.

## Graphics and prose

- One short method paragraph precedes the results; full equations, weights and the
  glossary belong in endnotes.
- The MacKinnon opener is followed by Forwards, Defensemen and Goalies, with commentary
  between sections. A same-age example is actually shown, with the rest linked separately.
- Single-panel images are the mobile default; two-panel alternatives are supplied.
  Three-across panels are removed. All figures were inspected at 390px phone width.
- Each pair shows its actual gap. Zero means identical matching values; lower is closer.
  Pools and their spreads differ, so raw gaps are not a universal quality grade across
  players, positions or models. Rounded labels do not determine rank.
- Burgundy consistently identifies the named target, including Forsberg; blue identifies
  the named comparison. The Cale overlay has its own explicit five-name legend.
- Alt text is supplied for every image, plus a 1200×675 preview. Alt text must be pasted
  into Substack when replacing images; PNG files alone cannot set the site's alt fields.

## Reproduce the primary article

```sh
uv run --locked --group analysis python -m avalanche_career_comps.feedback_analysis \
  --out local/article-feedback
```

The default omits career games from matching. Add `--include-career-games` for the
pool-preserving sensitivity control that retains career length. The older
`--omit-career-games` flag remains accepted for compatibility. Both controls are
calculated and recorded in the sensitivity files for either command.
Use an empty output directory. No database access or downloads occur.

The output includes `article-preview.html`, `article-explanations.txt`, `alt-text.csv`,
full and same-age graphics, raw results, changes and fingerprints. The explanatory text
describes the selected primary model; this workflow does not edit or publish the Substack post.

See [factual coverage and source notes](article-revision-notes.md) and
[official data provenance](sources.md).
