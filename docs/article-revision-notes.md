# Current article explanations and revision notes

These notes describe the primary rate-profile model selected on November 12, 2026
and supply article-ready explanations. Full careers remain primary, career games
are unweighted context, and PK
coverage cannot shrink the eligible pool. The original six-stat model is preserved as
a baseline; a separate control retains career length while fixing only the PK policy.

## Suggested reading order

1. Open with MacKinnon and Sakic as the first comparison, followed by the question the
   article asks. Identify it as the selected model's result rather than assuming every
   reasonable model produces the same match.
2. Give one short paragraph explaining the comparison, then show the remaining results
   in three sections: **Forwards**, **Defensemen**, and **Goalies**. Put one observation
   between groups instead of presenting eight uninterrupted images.
3. Use the Cale comparison to explain a distant nearest match. Explain any difference
   between its model and the roster model before naming a different closest player.
4. Follow with the Forsberg reverse search. Name the burgundy target and blue comparison
   consistently; the colors identify their roles in this comparison, not active/retired status.
5. Put formulas, exact weights, the glossary, source credit and the same-age supplement
   link in **Method notes** at the end.
6. Close with the reader question, a short statement of the next investigation, and the
   public GitHub link. Do not promise a particular next analysis unless the author has chosen it.

Suggested subtitle:

> Comparing today's Avalanche with the franchise's past, one statistical profile at a time.

## Short method explanation

> I compared each current Av with eligible former Avs at the same broad position, using
> NHL regular-season statistics through 2025–26. Scoring and shot rates are adjusted for
> era. I put the statistics on comparable scales, apply the stated weights and combine
> their differences into one statistical gap. The smallest gap identifies the closest
> available comparison; it does not mean the two players have identical styles or ability.

The primary model uses five rate statistics: goals, assists, shots, penalty minutes
and power-play points per 82 games. Career games describe the amount of observed
history and do not affect the match. The `--include-career-games` control retains
`log(1 + GP)` for sensitivity analysis only. Full-career and same-age are different
comparison windows, not age-curve estimates or projections of unfinished careers.

## PK coverage and the historical cutoff

The NHL's official time-on-ice records begin in **1997–98**, not 1995–96. The league's
[2023 All-Rookie Team release](https://media.nhl.com/site/vasset/public/attachments/2023/06/17229/AllRookieTeam.pdf)
states this on page 1. The saved usable PK observations also begin in 1997–98.

That date does not guarantee complete coverage afterward. In the saved audit, Forsberg
has usable PK records covering only **315 of 708** career games, with missing or failed
records extending through 1999–2000. Successful retrieval of a report is not evidence
that its minute fields are complete.

Current PK explanation:

> NHL ice-time records begin in 1997–98, and some later records are incomplete or fail
> consistency checks. I do not treat missing minutes as zero. When PK coverage is
> incomplete for an eligible comparison, I leave PK out of that comparison rather than
> remove otherwise eligible alumni.

The original baseline ranked only alumni with complete minutes when PK was active,
so it changed both the feature set and the candidate pool. That historical restriction
is preserved only for comparison; it does not apply to the primary article model.

## Weights and career games

The original six-stat baseline allocates weights of 17.5 to goals, 17.5 to assists, 15 to
shots, 10 to penalty minutes, 20 to log career games, and 10 to PP points. These sum to
90 and are normalized to 100% when PK is absent. PK adds 10 only under its declared
coverage rule. The resulting six-stat percentages are **19.44%, 19.44%, 16.67%, 11.11%,
22.22%, and 11.11%**, respectively.

With career games removed while the other relative weights are preserved, the five
remaining percentages without PK become **25% goals, 25% assists, 21.43% shots,
14.29% penalty minutes, and 14.29% PP points**. If PK were included under the revised
complete-pool rule, it would retain exactly 10%; the five other percentages would be
**22.5%, 22.5%, 19.29%, 12.86%, and 12.86%**, respectively. Rounding can affect the
displayed sum. In the full revised result set, ten skaters fall below the PK-use
threshold and nine require the coverage fallback. None of these 19 skater comparisons
uses PK; two of those skaters are omitted from the author's selected article figures.

These are declared descriptive weights, not empirically learned estimates. The old
model remains a labeled baseline, and changed matches are reported in the sensitivity
files. The [primary definitions](revised-method.md) and [shared equations](methods.md)
make the distinction explicit.

## Explaining the PP reference

The calculation retains the exact saved PP reference, **1.7682926829268293**, but prose
can display **1.77**. Its denominator is team-games, not individual player appearances:
league skater PP points are summed and divided by league team-games in 2025–26.

> I translated power-play production into the 2025–26 league environment, about 1.77
> power-play points per team-game. This sets the display units. Choosing another
> positive common reference would not change the matches because each statistic is
> subsequently scaled by its comparison pool's spread.

Goals and assists on the same power-play goal can produce several PP points, so this
reference is not a count of power-play goals per game. Keep full precision in the
calculation even when the article rounds it.

## Goalies

> Goalies use four equally weighted measures: save percentage above league,
> era-adjusted shots faced per appearance, and quality-start and shutout rates relative
> to each season's league. The latter two measure excess outcomes per 100 starts.
> Appearances and starts provide sample-size context and do not carry similarity weight.

Each feature receives **25%**. QS+ uses the NHL's supplied quality-start counts rather
than another provider's definition. These features describe statistical profiles; they
do not separate goalie ability from team defense or measure WAR or goals saved above
expected. See [the goalie equations](methods.md#goalies).

## Hughes and names

T.J. Hughes's saved NHL player identity is resolved, but his record contains no NHL
regular-season history through the completed **2025–26** cutoff. He cannot meet the
model's minimum of 50 observed NHL games. This does not imply that he has no experience
after the cutoff or no ability.

Suggested card explanation:

> No NHL history through 2025–26.

Suggested method note:

> T.J. Hughes is listed on the roster snapshot but has no NHL regular-season record
> within this analysis window, so I did not assign him a comparison.

Use one initial style consistently in display labels, such as **T.J. Hughes** and
**T.J. Galiardi**, while retaining the providers' original labels in preserved inputs.
NHL IDs, rather than displayed names, identify the players.

## Nearest-match gap and match quality

For each player, find the nearest other eligible profile. The **typical** gap means the
**median** of the historical alumni's own nearest-match gaps. A ratio divides a target's
nearest-match distance by that median; it does not measure difficulty, ability or a
probability.

For the original six-stat Cale calculation, `1.5695 / 0.3405 = 4.61`. Keeping career
length while fixing PK reproduces that number. Removing career length gives
`1.4011 / 0.2730 = 5.13`. Revised article-ready wording:

> Makar's gap from his nearest comparison is 5.1 times the median nearest-match gap
> among the 45 eligible former Avs defensemen.

The revised roster card and Cale overlay both name Bourque under the same five-stat
rules. The revised Forsberg search puts Sakic (1.140) and Rantanen (1.144) almost level;
the apparent lead should not be presented as meaningful evidence about playing style.
Do not reuse 4.6 from the six-stat run as a result of this five-stat run.

A panel's displayed raw gap should be labeled as a model distance with lower values
meaning closer profiles. Candidate pools and their standard deviations can differ, so
raw gaps from different pools are not a universally calibrated match-quality scale.
They are not percentages. Show the pool and feature definition in the method notes,
and use visible feature differences or a common-ruler diagnostic when discussing how
strong a particular analogy is.

## Source credit

> Statistics come from official NHL player pages and NHL Stats reports. The roster is
> a November 10, 2026 snapshot, and the analysis uses NHL regular-season records through
> 2025–26. The frozen inputs, method and reproduction code are available on GitHub.

[Data sources and provenance](sources.md) contains the report families, preserved
source URLs and coverage limits. Suggested final link:

> The data, code, and instructions to reproduce this analysis are available on
> [GitHub](https://github.com/quachanthony/avalanche-career-comps).
