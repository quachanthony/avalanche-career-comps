# Avalanche career comparisons

Which former Avalanche players have NHL careers most similar to the current roster?
This is the reproducible analysis behind Anthony's first Avalanche Substack article,
including the Cale Makar and Peter Forsberg comparisons.

**Start with the [article figures](figures/README.md), [method and equations](docs/methods.md),
or [data sources](docs/sources.md).** Full observed careers are the main analysis;
a separate through-age comparison is retained as an optional supplement.

![All Hail Cale](figures/all-hail-cale.png)

## Reproduce the article

From the repository root, with Python 3.11 or newer and [uv](https://docs.astral.sh/uv/):

```sh
uv sync --locked --group analysis --group dev
uv run --locked --group analysis python -m avalanche_career_comps.pipeline
```

Open `local/projects/avalanche-career-comps/article/index.html` in a browser.
The command verifies the input checksum, recalculates features and matches from the
included season-level data, checks the published numerical reference, and draws the
figures. No PostgreSQL setup, database credentials or data downloads are needed.

Choose a fresh destination for another run; existing nonempty directories are protected:

```sh
uv run --locked --group analysis python -m avalanche_career_comps.pipeline \
  --out local/projects/avalanche-career-comps/reproduction

uv run --locked --group analysis python -m avalanche_career_comps.pipeline \
  --no-figures --out local/projects/avalanche-career-comps/numerical-check
```

| Output | Contents |
| --- | --- |
| `full-career/` | Eight roster rows, **All Hail Cale**, and **Loosely, the Moose**, as PNG/SVG |
| `age-adjusted/` | Eight separate roster rows through the same season-age |
| `matches.csv` | Both windows' roster matches, distances and candidate counts |
| `*-results.json` | Features, weights, spreads, coverage decisions and distance contributions |
| `article-note.txt` | One explanation for the roster figures |
| `manifest.json` | Input/code/output checksums and Python/package versions |

## Scope and interpretation

The roster was collected on **November 10, 2026**. Statistics stop at the completed
**2025–26 regular season**. This is a frozen historical snapshot, not a live roster
or a current-season forecast.

Former skaters need **82 Colorado regular-season appearances**; goalies need **50**.
Colorado eligibility starts in 1995–96. Qualifying players' NHL records across all
teams count, including Quebec seasons. Forwards, defensemen and goalies are matched
separately. The roster search excludes current roster members from the alumni pool;
the Forsberg reverse search intentionally admits current as well as former Avs.
The displayed groups are the author's presentation choices, not inferred playing lines.
Hughes is labeled **Not enough data**. Result files retain additional ranked roster
players omitted from the article's images.

Skaters use era-adjusted goals, assists, shots and PP points per 82 games, unadjusted
penalty minutes per 82, and log-transformed career games. Complete PK minutes enter
for regular penalty killers when coverage permits. Goalies use save percentage above
league, adjusted shots faced per appearance, and season-relative quality-start and
shutout rates. [The method](docs/methods.md) gives exact formulas and weights.

**Why Barrie in the roster chart but Bourque in the Cale comparison?** The roster's
Makar comparison includes PK and ranks 29 alumni with complete records. The special
five-player radar uses six common statistics without PK across all 45 eligible alumni,
so Bourque and Ozolinsh can participate without invented minutes. Bourque is closest
under those shared-stat rules. Makar's nearest-match gap is 1.5695 versus a historical
median of 0.3405, or **4.61×**. This measures profile isolation within that pool, not
how much better he is. Career length contributes 38% of his squared gap from Bourque.

**Forsberg's reverse search** has 97 eligible past and present forwards. Rantanen,
Sakic and MacKinnon are the first three matches. A nearest match need not be mutual,
and statistical similarity does not establish identical styles or overall ability.

## Included data and provenance

- [Article inputs](research/article-inputs.json): a compact derived dataset of player-season
  counts, league environments, audited PK observations, and goalie starts/quality starts.
- [Input manifest](research/input-manifest.json): source URLs, retrieval times, response hashes,
  table grains and the warehouse publication fingerprint.
- [Expected results](research/expected-results.json): the numerical reference from the selected
  article outputs, checked against fresh calculations rather than used to generate them.

Stable NHL IDs join observations; names are labels. Traded-player totals and team stints
are handled explicitly. Missing minutes remain missing. No credentials, database dumps
or raw response archives are included. This reproduces the analysis **from normalized
season records**, not the warehouse ingestion itself. [Source notes](docs/sources.md)
describe that boundary and upstream attribution.

## Validation and limitations

```sh
uv run --locked --group analysis --group dev pytest -q tests
uv run --locked --group dev ruff check .
uv run --locked --group dev ruff format --check .
```

Tests cover calculations, exposure, age cutoffs, eligibility, missing values, stable
identities, PK coverage, goalie features and nearest matches. The offline pipeline checks
both roster windows and both special analyses against the published reference. Figures
are checked numerically and visually. This validates reproducibility, not predictive accuracy.

Weights are declared descriptive choices, not learned parameters. This is inspired by
prior hockey similarity work, **not a verbatim Hockey-Reference implementation**. Scoring
features overlap, missing PK coverage changes some pools, and current careers are unfinished.
See [methods](docs/methods.md) and [interpretation notes](docs/article-checks.md) before
reusing a claim.

## Project layout

```text
docs/                 method, sources and interpretation notes
figures/              ten final article PNGs and their manifest
research/             portable inputs, provenance and numerical reference
src/avalanche_career_comps/
  pipeline.py         single reproduction entry point
  analysis.py, era.py  career windows and era-normalized profiles
  special_teams.py    PP production, PK coverage and skater matching
  goalie_*.py         goalie performance inputs and features
  *_radar.py          article graphics
tests/                hand-auditable fixtures and offline reproduction checks
```

This standalone repository contains the article analysis and final figures. Abandoned
experiments, prior renders and the original warehouse/backfill tooling remain in the
author's separate local archive and warehouse project; they are not required here.
