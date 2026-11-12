# Interpreting the comparisons

These distinctions matter when reading the article or reusing its results. The complete
reproducible definitions are in [methods.md](methods.md).

* **Identify the fixed roster and cutoff.** Suggested addition: “The roster is the
  November 10, 2026 snapshot; the statistics stop at the completed 2025–26 regular
  season.” “Current” does not mean the reader's live roster or 2026–27 statistics.
* **State the weights and career-length transformation.** Career games enter as
  `log(1 + GP)`, although charts display actual GP. The six-stat weights are the
  seven-stat weights renormalized after PK is omitted. They are declared project
  choices, not fitted or externally validated weights. See
  [`analysis._rank`](../src/avalanche_career_comps/analysis.py) and
  [`special_teams.rank_without_lift`](../src/avalanche_career_comps/special_teams.py).
* **Broaden the PK coverage caveat.** Replace the parenthetical suggesting only
  pre-1995 minutes are missing with: “Historical PK minutes are incomplete; I required
  audited coverage for every season in the comparison window.” Forsberg has usable
  audited PK records for only 315 of 708 games, so later availability is not assumed.
  See `special_teams.pk_context` in the source linked above.
* **Explain Barrie versus Bourque before the Cale radar.** Suggested sentence: “For
  this broader comparison, I left PK minutes out for everyone so Bourque and Ozolinsh
  could be included despite incomplete minutes.” The roster's PK-covered pool has
  29 defensemen; the common six-stat Cale analysis has 45. See
  [`makar_compact.consolidate`](../src/avalanche_career_comps/makar_compact.py).
* **Keep 4.6× limited to the measured gap.** Suggested wording: “Makar's nearest-match
  gap is 4.6 times the median nearest-match gap among the 45 eligible former Avs
  defensemen.” It is not a quality multiplier, NHL-wide claim or probability of seeing
  another Makar. Career length contributes about 38% of his squared gap from Bourque.
  The article's eye-test judgment can remain an opinion, separate from that number.
* **Do not infer Forsberg has no present-day analogue from his absence as a first
  choice.** Nearest matches need not be reciprocal, and reversing the search changes
  the eligible pool and its scales. Suggested transition: “Forsberg did not appear as
  anyone's closest match, so I reversed the question and looked for his closest
  comparison among past and present Avs.” See
  [`reverse_similarity.compare`](../src/avalanche_career_comps/reverse_similarity.py).
* **Keep goalie labels precise.** QS+/SO+ are league-relative rates rather than raw
  percentages. The NHL's quality-start threshold is strictly greater than .900; the
  code uses its supplied `qualityStart` counts. All four goalie features have 25%
  weight. These are not WAR or GSAx. See
  [`goalie_performance.features`](../src/avalanche_career_comps/goalie_performance.py)
  and [`goalie_revision.WEIGHTS`](../src/avalanche_career_comps/goalie_revision.py).

See [the equations and variable definitions](methods.md) for the separate assist
denominator, PP reference rate, population standard deviations and normalized weights.
