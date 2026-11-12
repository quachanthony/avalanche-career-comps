# Data sources and prior work

## Data used for the article

All player and league statistics used in the final comparisons come from official NHL
public interfaces. Sources were preserved in November 2026; the roster date is November
10 and statistical records are cut off at the completed 2025–26 regular season. The
reproduction uses normalized derived inputs in `research/article-inputs.json`, with
provenance in `research/input-manifest.json`. It does not need live requests, database
credentials or the original local downloads.

| Input | Official source and scope | Use |
| --- | --- | --- |
| Roster | [NHL Web Colorado roster](https://api-web.nhle.com/v1/roster/COL/current), captured November 10, 2026 | Fixed target identities; the live URL can change |
| Colorado appearances | [NHL Stats skater summary](https://api.nhle.com/stats/rest/en/skater/summary) and [goalie summary](https://api.nhle.com/stats/rest/en/goalie/summary), aggregate regular seasons from 1995–96, team ID 21 | Eligibility only; Quebec does not count |
| Full careers | NHL Web player landing, e.g. [Peter Forsberg, NHL ID 8458520](https://api-web.nhle.com/v1/player/8458520/landing) | NHL regular-season team stints, counts and stable player IDs |
| Scoring and PP points | [NHL Stats skater summary](https://api.nhle.com/stats/rest/en/skater/summary), one combined player-season; [goalie summary](https://api.nhle.com/stats/rest/en/goalie/summary) for goalie scoring contributions | Separate league goal, assist and PP environments; PP points reconciled to career games, goals and assists |
| League scoring and shots | [NHL Stats team summary](https://api.nhle.com/stats/rest/en/team/summary), regular-season team-seasons | Team-games, reconciled goal totals, and games-weighted reported shot rates for seasonal era factors |
| PK minutes | [NHL Stats skater time-on-ice](https://api.nhle.com/stats/rest/en/skater/timeonice) plus saved NHL player totals | Audited whole-window minutes; incomplete or conflicting seasons remain unavailable |
| Goalie starts, shutouts and shots | [NHL Stats goalie summary](https://api.nhle.com/stats/rest/en/goalie/summary) and NHL Web player landing | Full-career counts/exposure and contemporary league rates |
| Goalie quality starts | [NHL Stats goalie advanced](https://api.nhle.com/stats/rest/en/goalie/advanced), including combined player-season league records | Official `qualityStart` counts and each season's quality starts per start |

API links above identify the providers and report families. The manifest records the
specific query parameters, saved-source hashes and retrieval provenance used by this
version. An upstream revision or a fresh live download may differ from the article's
frozen records. Public availability is not a transfer of the provider's data rights;
source terms remain separate from the project's code.

The NHL describes quality starts as starts above .900 save percentage in
[its Quick retrospective](https://www.nhl.com/news/nhl-edge-stats-behind-jonathan-quick-goaltending-retirement).
See also [the 2019 statistics-section announcement](https://www.nhl.com/news/nhl-develops-new-stats-section-to-compare-teams-and-players-312630988).
The reproduction uses supplied `qualityStart` counts, rather than reclassifying games
from a prose description or another provider's definition.

## Source reconciliation and coverage

One player/team/season/stint is intentionally aggregated to one player-season. Stable
NHL IDs link records. Combined traded-player rows are not added to their team stints.
The analysis never uses names as identity keys or substitutes missing statistics with
zeroes.

The source-preserving warehouse was used to audit the November 11 historical publication.
Its fingerprint was
`cb2838f663fd83b2cf5cd106bc31c7be63c5456cd413531da28aeb2f2f2e261b`.
All 6,222 historical regular-season skater summaries and PP records for 1986–87 through
1994–95 reconciled to the previously frozen official career inputs. Their ice-time
report rows had null total, PP and PK minutes. A successful download does not establish
usable ice time. Some later minute histories also fail the audit; coverage is checked
for each complete comparison window.

Official Colorado summary counts determine eligibility because historical player-game
participation in the warehouse is incomplete. The public reproduction needs the derived
research inputs, not a live warehouse rebuild. Goalie counts were reconciled across
15 careers, 190 player-seasons and 3,837 league goalie-seasons. A documented five-second
2016–17 Anderson TOI discrepancy is retained in the source audit and does not affect the
starts-based features.

## Prior work reviewed

The following sources informed a targeted method discussion during the exploration,
beginning November 10, 2026, after the initial implementation. This was not a systematic
literature review. Primary pages and indexed official-domain text were rechecked on
November 12. These sources do not establish that the project's weights have been
empirically validated, and the final model does not reproduce a provider's complete
similarity system.

* [Hockey-Reference, Adjusted Statistics](https://www.hockey-reference.com/about/adjusted_stats.html)
  provides a scoring-environment precedent with separate goal and assist adjustments.
  This project's method is simpler: it does not remove each player's own contribution
  from league denominators or reproduce Hockey-Reference's schedule and roster-size
  adjustments. The original review used official-domain indexed text when direct access
  returned HTTP 403.
* [Thibaud Chatel, Adjusting Stats to the Evolution of Scoring around the World (2024)](https://thibaudchatel.substack.com/p/adjusting-stats-to-the-evolution)
  describes goals and assists as different environments. The final method explicitly
  gives those statistics separate league denominators.
* [Evolving-Hockey, Skater Similarity Scores](https://evolving-hockey.com/glossary/skater-similarity-scores/)
  illustrates weighted Euclidean distance on standardized positional datasets. Its
  even-strength, PP and SH multipliers reflect league ice-time shares. Its features,
  comparison windows and weighting scheme differ from this project.
* [Olivestam et al., Characterizing Playing Styles for Ice Hockey Players (LINHAC 2024)](https://ecp.ep.liu.se/index.php/linhac/article/view/1038)
  uses event-derived skill vectors and fuzzy clustering to characterize playing styles.
  The article does not fit those skill vectors or clusters.
* [Berry, Reese and Larkey, Bridging Different Eras in Sports (1999)](https://doi.org/10.1080/01621459.1999.10474163)
  connects overlapping careers through a hierarchical model of player, era and age
  effects. The article uses league-rate rescaling, not that model.
* [Schuckers, Lopez and Macdonald, Estimation of Player Aging Curves Using Regression and Imputation (2023 revision)](https://arxiv.org/html/2110.14017v2)
  discusses season-relative scoring and selection in aging analysis. The article's
  age-aligned comparison only truncates observed careers; it estimates no aging curve.
* [Ramaswamy, Rastogi and Shim, Efficient Algorithms for Mining Outliers from Large Data Sets (2000)](https://doi.org/10.1145/335191.335437)
  supplies a distance-based outlier precedent. Dividing Makar's nearest-match gap by
  the alumni median is this project's descriptive summary, not a formal outlier test.

Hockey-Reference's [season Point Shares similarity method](https://www.hockey-reference.com/about/similar.html)
was explored separately. It sorts adjusted seasonal Point Shares from best to worst and
applies season-rank weights of 1.00, 0.95, 0.90 and so on. Those are weights on ranked
seasons, not weights on goals, assists or other individual statistics. Direct access
returned HTTP 403 in the recheck; the official-domain indexed method text was readable.
The final article uses the six/seven-feature model documented in [methods.md](methods.md),
with the four-feature goalie revision. No Point Shares, WAR, hits, debut age or recent
scoring-lift feature enters these published comparisons.
