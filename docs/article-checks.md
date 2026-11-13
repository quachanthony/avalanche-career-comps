# Interpreting the current comparisons

The primary article model uses full observed careers and five rate statistics. Career
games are unweighted context; the separate same-age run is a sensitivity check. The
complete definitions are in [the current method](revised-method.md).

- **Use the fixed roster and cutoff.** The roster is the November 10, 2026 snapshot;
  statistics stop at the completed 2025–26 regular season. “Current” does not mean a
  live roster or current-season statistics.
- **Distinguish rates from career length.** The matching features are adjusted goals,
  assists, shots and PP points per 82 games plus unadjusted PIM/82. Displayed GP shows
  exposure and does not affect the score. Full-career averages can still reflect
  late-career decline, and current players' careers remain unfinished.
- **State the weights.** Goals and assists each receive 25%, shots 21.43%, PIM 14.29%
  and PP points 14.29%, rounded. These are declared descriptive choices, not learned
  or externally validated weights. See
  [`feedback_analysis.production_weights`](../src/avalanche_career_comps/feedback_analysis.py).
- **Preserve eligible players when minutes are missing.** Official NHL time-on-ice
  records begin in 1997–98, and later records can also be incomplete or disagree.
  Missing minutes are never zero. PK is omitted unless the target and every eligible
  candidate have complete audited minutes; it never removes an eligible alumnus.
  No full-career skater comparison in this dataset uses PK under that rule.
- **Use the same Makar headline in both places.** Both the roster card and the Cale
  overlay compare all 45 eligible alumni with the same five rate statistics and name
  Ray Bourque. The old Barrie result came from a different model with a PK-restricted
  pool; it belongs only to the historical baseline.
- **Interpret 5.13× as a distance ratio.** Makar's nearest-match gap is 1.401108,
  versus a median historical nearest-match gap of 0.272958. Their ratio is 5.133045.
  It is not a quality multiplier, difficulty measure, probability or NHL-wide claim.
  The old 4.61× value includes career length and must not label the primary model.
- **Treat the Forsberg ordering cautiously.** Sakic and Rantanen have gaps of 1.139993
  and 1.143946—almost tied. MacKinnon is third. Nearest matches need not be reciprocal,
  and reversing the search changes both the eligible pool and its statistical ruler.
  Absence from a roster player's first choice does not establish lack of resemblance.
- **Keep goalie labels precise.** SV+, adjusted SA/G, QS+ and SO+ each receive 25%.
  The NHL's supplied quality-start counts are used. These descriptive rates do not
  measure WAR or GSAx and do not isolate the goalie from team defense. See
  [the unchanged goalie equations](methods.md#goalies).
- **Read the gap within its model.** Lower weighted statistical distance means closer
  recorded profiles, not a higher similarity percentage or a calibrated quality grade.
  Different pools and feature sets use different spreads. Radar overlap is not the score.
- **Keep colors tied to roles.** Burgundy means the named target, including Forsberg;
  blue means the named comparison. The Cale overlay has an explicit five-player legend.

The baseline remains reproducible, and the `--include-career-games` control separates
career length from the PK policy change. Neither control is the primary article model.
