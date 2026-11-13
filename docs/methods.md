# Original baseline method and shared equations

> **Historical baseline:** This document records the original six/seven-stat model,
> including its former PK pool restriction and weighted career length. It is not the
> primary article method. The selected [current rate-profile method](revised-method.md)
> uses five rate statistics, preserves the full eligible pool and leaves career games
> unweighted. The era-adjustment and distance equations below remain shared.

The question is which eligible former Avalanche player has the closest statistical
career profile to each player on the saved Colorado roster. This is a descriptive
comparison of recorded careers. It does not predict future seasons or estimate overall
player value.

## Players and career windows

The roster was captured on November 10, 2026. All statistical comparisons stop at the
completed 2025–26 regular season; 2026–27 is excluded. The saved source calendar begins
in 1979–80. Playoffs and preseason are excluded.

An alumnus needs at least 82 Colorado regular-season appearances for skaters or 50 for
goalies, counted from 1995–96 onward. Quebec games do not establish eligibility. Once a
player qualifies, his NHL seasons with all teams, including Quebec, enter his career
profile. Current roster members are excluded from the ordinary alumni pool. Forwards,
defensemen and goalies have separate pools. Current skaters need 50 observed NHL games;
current goalies need 25. Missing required statistics prevent a comparison.

The article's main images use full observed careers through the cutoff. Current
players' careers are unfinished. The optional age-aligned version truncates alumni at
the current player's season-age, defined as age on February 1 of the season's ending
year. It estimates no aging curve or future performance. An alumnus whose career ended
more than one age-year before the requested age is excluded; a one-year-short comparison
is retained with a flag.

NHL player IDs join the sources. Legitimate team stints are combined to one
player-season; a combined traded-player total is never added again. Counts and games
are summed before rates are calculated. Eligibility and the career statistics have
different scopes: Colorado games select the players, while all NHL teams describe
their careers.

## Skater features and era adjustment

For player $p$, season $s$, and statistic $k$, let $C_{p,s,k}$ be the
recorded count, $G_{p,s}$ the player's games, and $T_s$ league team-games. One
physical game contributes two team-games. The seasonal league environment is

$$
L_{s,k}=\frac{\text{league total of statistic }k\text{ in season }s}{T_s}.
$$

Goals, assists, shots and power-play points receive separate multiplicative adjustments:

$$
C^{\mathrm{adj}}_{p,s,k}=C_{p,s,k}\frac{R_k}{L_{s,k}},
\qquad
X_{p,k}=82\frac{\sum_s C^{\mathrm{adj}}_{p,s,k}}{\sum_s G_{p,s}}.
$$

The reference rates $R_k$ are 3 goals, 5 assists and 30 shots per team-game. The
power-play reference is the saved 2025–26 league skater power-play-points rate,
approximately 1.7683 per team-game. These are reference units, not estimated optimal
rates. The goal and assist league totals include goalie contributions as well as
skaters. The goal totals reconcile to team goals and already exclude shootout decisions;
no shootout-win correction is subtracted again. Power-play points count player goals
plus assists on power-play goals, so their
league total is not the number of power-play goals.

Penalty minutes are not adjusted for era:

$$
X_{p,\mathrm{PIM}}=82\frac{\sum_s\mathrm{PIM}_{p,s}}{\sum_s G_{p,s}}.
$$

Career length enters as $X_{p,\mathrm{GP}}=\log(1+\sum_s G_{p,s})$, using the
natural logarithm to reduce the influence of very long careers. Charts display actual
career games beside that spoke. Per-82 rates describe production per game; they do not
assume a player actually played 82 games or adjust for minutes, teammates or deployment.

### Conditional penalty-kill feature

PK minutes per game enter only when the target averages at least one minute per game,
has audited minutes for the entire comparison window, and at least two eligible alumni
also have complete audited minutes. The ranking then uses only those covered alumni.
Their statistical scales are recomputed on that covered pool.

$$
X_{p,\mathrm{PK}}=\frac{\sum_s\mathrm{PKSeconds}_{p,s}}{60\sum_s G_{p,s}}.
$$

If these conditions fail, PK is omitted and the full otherwise-eligible pool is used.
Missing minutes are not zeroes. Early coverage is incomplete, and post-1995 coverage is
not automatically assumed complete. PP points remain usable independently of PP minutes.

### Weights and distance

The project declares the following weights. They are not fitted to outcomes, expert
pair labels or a holdout set, and are not claimed to be uniquely correct. They are also
not Hockey-Reference's published similarity formula.

| Feature | PK included | PK omitted |
| --- | ---: | ---: |
| Adjusted goals / 82 | 17.5% | 19.444…% |
| Adjusted assists / 82 | 17.5% | 19.444…% |
| Adjusted shots / 82 | 15% | 16.666…% |
| Penalty minutes / 82 | 10% | 11.111…% |
| Log career games | 20% | 22.222…% |
| Adjusted PP points / 82 | 10% | 11.111…% |
| PK minutes / game | 10% | omitted |

The six-stat weights are the first six PK-inclusive weights divided by 0.90, preserving
their relative proportions. Debut age, recent scoring lift and hits are excluded.

For each target's final eligible pool of $n$ alumni, calculate the mean $\mu_k$
and population standard deviation $\sigma_k$ of each feature:

$$
\mu_k=\frac{1}{n}\sum_{h=1}^{n}X_{h,k},\qquad
\sigma_k=\sqrt{\frac{1}{n}\sum_{h=1}^{n}(X_{h,k}-\mu_k)^2}.
$$

The weighted Euclidean distance between target $p$ and candidate $h$ is

$$
D(p,h)=\sqrt{\sum_k w_k\left(\frac{X_{p,k}-X_{h,k}}{\sigma_k}\right)^2}.
$$

Weights sum to one. A zero candidate spread uses a scale of one rather than dividing
by zero. The smallest distance identifies the closest match; ties use NHL player ID.
The target is not used to fit the ordinary alumni scales. Distances are not similarity
percentages. Different pools and features give different rulers, so distances across
roster players are not a universal ranking of who is easiest to match.

## Goalies

Goalies use four features at 25% each, with the same standardized-distance calculation.
Let $A_{p,s}$ be shots faced, $B_{p,s}$ goals allowed, and
$q_s=\text{league goalie goals allowed}/\text{league goalie shots faced}$.

* **SV+** is save percentage above the contemporary league, weighted by shots faced:
  $100[\sum_s A_{p,s}q_s-\sum_s B_{p,s}]/\sum_s A_{p,s}$, displayed in
  percentage points. The stored feature omits the factor of 100; standardization makes
  these equivalent distance units.
* **SA/G** is era-adjusted shots faced per appearance:
  $\sum_s A_{p,s}(30/L_{s,\mathrm{shots}})/\sum_s G_{p,s}$.
* **QS+** and **SO+** are excess quality starts and shutouts per 100 starts. For either
  event, with player count $E_{p,s}$, player starts $S_{p,s}$, and league
  event-per-start rate $e_s$, use
  $100[\sum_s E_{p,s}-\sum_s S_{p,s}e_s]/\sum_s S_{p,s}$.

QS counts are the NHL's supplied `goalie/advanced` `qualityStart` counts, using its fixed
save-percentage threshold greater than .900, rather than Hockey-Reference's quality-start
definition. The season-relative comparison adjusts the frequency of those events for
era. Appearances and starts are exposure and displayed context; neither carries a
separate similarity weight. These features do not adjust for shot quality or isolate a
goalie's performance from his team's defense. No WAR, GSAx or Point Shares enter the
published model.

## The separate Makar comparison

The roster model matches Makar to Barrie using PK and 29 alumni with complete minutes.
The **All Hail Cale** radar instead compares Makar, Bourque, Barrie, Ozolinsh and Liles
on the same six shared features, consistently omitting PK. Its pool contains all 45
eligible former Avs defensemen. Bourque is Makar's closest match under this shared-stat
definition. This deliberate coverage change explains the two different names.

The unusualness calculation uses one fixed set of historical scales and weights. Add
Makar to the 45 alumni, exclude self-matches, and find each player's nearest other
profile among the remaining 45:

$$
d(p)=\min_{q\ne p}D(p,q),\quad
m=\operatorname{median}_{h\in H}d(h),\quad
U(p)=\frac{d(p)}{m},
$$

where $H$ is the 45-player historical pool. Adding Makar leaves the historical nearest
gaps unchanged; the pipeline verifies this. The median is approximately 0.34048.
Makar's nearest match is Bourque at 1.56952, giving **4.61×**. Bourque's own nearest
match is Blake at 1.25156, giving **3.68×**. These values describe different pairs;
nearest matches need not be mutual. On the optional dot plot, spacing between two
players' dots is not their pairwise statistical distance.

This is an empirical description of unusualness within the selected franchise pool,
not a probability, a significance test or a claim about all NHL defensemen. Career
length contributes about 38% of the squared Makar–Bourque gap. The 4.61× value therefore
does not measure scoring alone or mean Makar is 4.61 times better.

## The reverse Forsberg comparison

**Loosely, the Moose** makes Forsberg the target and admits eligible past **and current**
Avs forwards at the same 82-game Colorado threshold. Self-matches are excluded. It uses
full observed careers, the same six-stat weights and a new shared 97-forward pool.
Forsberg's incomplete minutes leave PK out. The closest three are Rantanen, Sakic and
MacKinnon. Reversing the question changes both the candidate pool and its scales;
absence from another player's first-choice match is not evidence of no resemblance.

## Reading the radars and assessing the result

Each spoke plots $z_{p,k}=(X_{p,k}-\mu_k)/\sigma_k$, using the same ruler for
both players in that chart. The darker ring is the feature-wise candidate average.
The polygon shows the feature profile without multiplying its coordinates by the
distance weights. Shaded overlap is not a score. Outward means more of the statistic,
including penalty minutes and career length; it does not consistently mean better.

These are explored descriptive analogues, not validated predictions or causal results.
Career length, late-career decline, incomplete current careers, sample-size differences,
feature correlations and the franchise eligibility screen can affect matches. Goals,
assists and PP points overlap statistically, and covariance is not removed. Era
rescaling captures league scoring conditions, not changes in talent, rules, usage or
defensive value. Changing the weights or coverage policy can change the nearest player.
The code checks arithmetic, scope and reproducibility; those checks do not validate the
scientific choice of weights.
