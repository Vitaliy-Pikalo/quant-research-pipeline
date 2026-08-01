# H10 — Fed Beige Book district sentiment vs regional bank returns

date: 2026-07-31
budget: $0, free/public data only
status: **not supported**

## tl;dr

Third hypothesis tested end to end through the same purged-CV / BH-FDR / deflated-Sharpe pipeline as H8 and H9. Third negative.

The pre-specified primary signal — a district's Beige Book tone scored against its own trailing baseline — has essentially zero relationship to that district's regional-bank basket, excess of KRE. Pooled IC 0.015 (p=0.56), zero of twelve districts significant, walk-forward IC flipping sign, long/short strategy loses money before costs.

One of six secondary specifications did survive FDR: tone *change* vs the district's own previous release, at a 42-trading-day horizon. It held up under a block bootstrap and produced a positive net-of-cost Sharpe of 0.36. It then failed split-half replication and collapsed to a deflated Sharpe of **0.18** against the project's honest cumulative trial count of 75. That is the correct outcome for a weak effect found on the sixth of six specs, and it is reported here rather than buried because it is the most interesting near-miss of the three hypotheses.

| | value |
|---|---|
| primary spec pooled IC | 0.0153 (p=0.557) |
| districts surviving BH-FDR(10%) | 0 / 12 |
| primary L/S net Sharpe | −0.238 |
| best secondary spec | tone change, 42d: IC 0.0704 |
| that spec, bootstrap p | 0.0186 |
| that spec, net Sharpe | 0.356 |
| that spec, DSR @ 75 trials | **0.182** |

## theory

Dossier idea #20. The Beige Book is compiled from 12 regional Fed districts and then synthesised into a national summary. If district-level tone carries information about local conditions not yet reflected in that district's regional banks, a district whose tone improves relative to its own recent history should see its banks outperform the regional-bank sector over the following weeks.

## data

Everything below was scraped or pulled fresh. Nothing purchased.

**Sentiment.** 131 Beige Book releases, 2010-01-13 to 2026-07-15, all 12 districts each, 1,572 district-observations. Scored with the Loughran-McDonald financial dictionary via `pysentiment2`.

**Prices.** 33 regional banks/REITs (3 per district by HQ location) plus KRE as the sector benchmark, daily, via yfinance.

### what the data build actually cost

The scraper took six iterations. This is worth recording because four of the failures would have produced a *result* rather than an error.

| version | failure | consequence if undetected |
|---|---|---|
| v1 | regex built against rendered text, not raw HTML | 0 releases — loud failure, harmless |
| v2 | index-page discovery missed 2017–2023 and 2026 | silent 7-year hole in the panel |
| v2 | 5 releases fell back to a `YYYY-MM-01` placeholder date | stem month ≠ release month: `202505` is the *May* book but was **published 4 June**. Forward returns measured from ~5 weeks before the information was public. Look-ahead bias, in the direction that manufactures signal |
| v4 | 2024–2026 district pages scored whole, nav menu included | ~850 words of identical boilerplate per observation. word_count 1496 vs 640, polarity variance −40%. A structural break at the exact date the Fed changed its template, which a district-relative z-score reads as a real simultaneous cross-district sentiment shift |
| v5 | footer-marker fix for one parser truncated another | 46 releases lost — loud failure |
| v6 | one Fed-side markup typo (`<h4>St. Louis</h4>`) | 1 district-observation |

The date bug and the boilerplate bug are the dangerous ones: both are silent, and both push toward false positives.

Final dataset checks, all passing:

- 131/131 release dates fall on a **Wednesday** (the Beige Book's publication convention — an independent validation of the date extraction, which is drawn from the `BeigeBook_YYYYMMDD.pdf` filename each release links)
- all 131 releases carry a full 12 districts
- word counts comparable across all five page layouts (587–661 mean)
- no polarity discontinuity at the 2011 / 2017 / 2024 template changes; the large moves land on 2020 (−0.27) and 2022 (−0.32), which is economics

### price panel: survivorship bias, caught

The first price pull silently dropped 4 of 36 tickers. They were not missing at random — every one is an acquisition target:

| ticker | district | event |
|---|---|---|
| BHLB | Boston | merged with BRKL → Beacon Financial, Sep 2025 |
| NYCB | New York | renamed Flagstar Financial, Oct 2024 |
| SNV | Atlanta | merged into Pinnacle Financial, Jan 2026 |
| CMA | Dallas | acquired by Fifth Third, delisted Feb 2026 |

Acquisition announcements are large positive return events. Dropping precisely the acquired names biases every affected district's basket. Recovery attempts, judged on the data rather than the story:

- **BHLB → BBT: accepted.** 2010 $19.54 / 2018 $42.40 / 2020 $10.72 matches Berkshire Hills, not BB&T ($26/$50/→Truist), and the series runs continuously across BB&T's Dec-2019 ticker retirement. Same listing, renamed.
- **NYCB → FLG: accepted.** −38% on 2024-01-31 matches NYCB's collapse exactly; levels are 3× throughout from a reverse-split adjustment, which does not affect returns.
- **CMA → FITB: rejected.** The proxy series is bit-identical to the FITB already in the Cleveland basket. Using it would have double-counted one bank across two districts.
- **SNV → PNFP: rejected.** Legacy Pinnacle, a different company.

Separately, **BRKL** appeared to pull successfully but returned **18 rows starting 2026-07-07** — the ticker was recycled after Brookline merged into Beacon. The apparent success was an unrelated instrument.

Net: Boston, Atlanta and Dallas run on 2 constituents instead of 3.

## method

- **Benchmark: KRE, not SPY.** H8's headline lesson was that a raw-return "edge" was market beta. This test is about district-relative performance *within* regional banks, so the benchmark is the sector. Using SPY would leave the entire regional-banking factor in the residual and repeat H8's mistake with different data.
- **Feature: district-relative, not cross-sectional level.** Reserve Banks differ persistently in house writing style and their staff changes over time. Ranking raw polarity across districts would mostly rank prose. Primary feature is each district's polarity z-scored against its own trailing 8 releases (~1 year).
- **Timing.** The Beige Book publishes at 2:00 pm ET, so the release-day close is already partly informed. All entries are at the close of the **first trading day after** release. This gives up any same-day drift deliberately.
- **Baskets** equal-weight whatever constituents exist on each date, so late listings (CUBI from 2012-03, MSBI from 2016-05) join when they start trading rather than voiding the district.
- **Validation** uses the project's existing `cv.PurgedKFold` (label horizon scaled to the return window, 5-day embargo), `stats.benjamini_hochberg`, `stats.deflated_sharpe_ratio`, and `costs.apply_transaction_costs` at 20 bps round-trip, full turnover.

### trial accounting

Deflated Sharpe means nothing without an honest denominator.

| source | trials |
|---|---|
| H9 FX carry, three runs | 46 |
| H8 13F copycat | 6 |
| H10 pooled (2 features × 3 horizons) | 6 |
| H10 per-district | 12 |
| H10 strategy | 1 |
| H10 stress-test checks | 4 |
| **cumulative** | **75** |

## results

### primary spec — tone z-score vs own baseline, 21 days

| test | result |
|---|---|
| pooled IC | 0.0153, p=0.557 (n=1,464) |
| districts with p<0.05 | 0 / 12 |
| surviving BH-FDR(10%) | 0 / 12 |
| sign agreement with theory | 7 / 12 |
| walk-forward folds positive | 3 / 5 (mean IC 0.016, sd 0.055) |
| L/S mean return per release | −0.041%, hit rate 46.7% |
| gross Sharpe / net Sharpe | −0.040 / −0.238 |
| DSR @ 71 trials | 0.0004 |

Nothing there. Per-district ICs range from −0.156 (San Francisco) to +0.134 (Atlanta) with no district clearing FDR, which is what twelve draws from noise looks like.

### secondary specs

| feature | horizon | IC | p | survives BH-FDR(10%) |
|---|---|---|---|---|
| z-score | 5d | 0.0038 | 0.883 | no |
| z-score | 21d | 0.0153 | 0.557 | no |
| z-score | 42d | 0.0272 | 0.300 | no |
| tone change | 5d | 0.0183 | 0.470 | no |
| tone change | 21d | 0.0508 | 0.046 | no |
| **tone change** | **42d** | **0.0704** | **0.0058** | **yes** |

### stress test of the one survivor

The 42-day horizon is where releases stop being independent: Beige Books are ~35 trading days apart, so consecutive 42-day windows overlap, and all 12 districts at a release share the same calendar window. The pooled test assumes 1,536 independent observations; there are ~128 independent blocks. It is also the longest horizon tested and the sixth of six specs — the classic profile of a wider confidence interval mistaken for a finding.

| check | result | verdict |
|---|---|---|
| A — block bootstrap by release, 10,000 resamples | IC 0.0704, 95% CI [0.0110, 0.1275], p=0.0186. SE inflated 1.18× over parametric | **pass** — naive p overstated 3×, but survives |
| B — non-overlapping subsample | offset 0: IC 0.047, p=0.194 · offset 1: IC 0.090, p=0.013 | **fail** — one half carries the result |
| C — purged walk-forward | 4/5 folds positive, mean 0.064, sd 0.057, one fold −0.012 | **mixed** — better than H9's every-fold sign flip, not stable |
| D — tradability | +0.641%/release, hit 55.5%, t=2.07 (p=0.040), gross Sharpe 0.518, net 0.356 | **pass** |
| **DSR @ 75 cumulative trials** | **0.182** (0.936 at n_trials=1) | **fail** |

Two further caveats on check D: the 42-day windows overlap, so those strategy returns are autocorrelated and the Sharpe is itself overstated; and return kurtosis is 7.1, so the distribution is fat-tailed.

**Conclusion on the survivor:** a weak effect that cannot be distinguished from the best of six specifications tested on overlapping windows. It is not nothing — it survived a bootstrap that killed a third of its significance, and it made money net of costs — but it fails replication in half the sample and does not clear the multiple-testing bar. Reported as a near-miss, not a result.

## verification

Run before writing this up, not after.

| check | result |
|---|---|
| pipeline test suite (`pytest`) | **49 passed** — `cv.py`/`stats.py`/`costs.py` used unmodified, so H10 is judged by the same code as H8 and H9 |
| entry date strictly after release date | ✅ all 1,572 rows, gap 1–2 calendar days |
| z-score uses only prior releases | ✅ independently recomputed from scratch, max difference 1.3e-13 |
| forward return recomputed from raw cumulative series | ✅ spot-check matches stored value exactly |
| first z-score observation never precedes the 9th release of that district | ✅ |
| KRE benchmark excluded from every district basket | ✅ (would otherwise partially cancel against itself) |
| no ticker assigned to two districts | ✅ 33 tickers, 12 districts |
| districts available for cross-sectional ranking | 12.0 mean per release |

District map spot-checked constituent by constituent against HQ location. 32 of 33 are unambiguous. **One is not: FMBH (First Mid Bancshares, Mattoon, Illinois).** The Eighth District covers "44 counties in southern Illinois" and Coles County sits near the 7th/8th boundary, so FMBH may belong in Chicago rather than St. Louis. Unresolved; affects 1 of 33 constituents and one name in each of two districts' baskets.

## limitations

Stated plainly, not fixed.

1. **The district mapping is the weakest part of the design.** Banks are assigned to districts by HQ location, but several constituents are national franchises whose returns have little to do with their home district's economy. U.S. Bancorp is a ~$600bn national bank nominally representing Minneapolis; Truist is a national franchise representing Richmond. For those names the district label is nominal, which dilutes any genuine district-level effect toward zero. **This is the single most likely reason for a false negative here.**

   The obvious response — re-run on a "local banks only" subset — was deliberately **not** done. Any subset rule invented after seeing a null result is a researcher degree of freedom, and picking the subset that rescues the hypothesis is exactly the failure mode this pipeline exists to prevent. The disciplined version is a pre-registered follow-up using an objective locality measure, e.g. FDIC Summary of Deposits share-of-deposits-within-district (free, public), fixed before looking at returns.

2. **3 of 36 constituents are permanently unrecoverable**, and their absence is not random — all were acquisition targets. Boston, Atlanta and Dallas run on 2 names.

3. **2 of 133 releases** (2011-03-02, 2015-03-04) could not be scraped.

4. **Loughran-McDonald is a bag-of-words dictionary.** It has no negation handling and no notion of "activity declined *less* than expected." The Beige Book's characteristic hedged prose ("modest", "slight", "little changed") is close to the worst case for it. A weak measured signal may reflect a weak measurement instrument rather than a weak underlying effect.

5. **Sentiment is measured on the whole district report**, mixing sectors — agriculture, manufacturing, tourism, CRE — while the return series is banks only. A banking-specific extract would be a tighter test.

6. **Regime dependence untested.** `regime.py` exists in the pipeline and was not applied here; the walk-forward folds hint the relationship may be stronger post-2019 (folds 4 and 5 carry the positive ICs), but chasing that after the fact is the same forking-path problem as limitation 1.

## bottom line

Three hypotheses, three real datasets, three negatives. The pipeline continues to do the job it was built for: it killed a spec that looked like a 0.94-probability result when treated in isolation, and it did so on the arithmetic of an honest trial count rather than on judgement.

The Beige Book case is the closest of the three to something real. The right next move is not to re-slice this data — it is to fix the design flaw that most plausibly caused the null (limitation 1), pre-register it, and run it once.

## files

| file | contents |
|---|---|
| `beige_book_sentiment_final.csv` | 1,572 district-release sentiment observations, 2010–2026 |
| `regional_bank_prices_clean.csv` | 33 banks + KRE, daily, audited |
| `district_constituent_report.csv` | per-constituent status and recovery notes |
| `run_beigebook_backtest.py` | main backtest |
| `h10_stress_test.py` | four-check stress test of the surviving spec |
| `h10_pooled_results.csv` / `h10_district_results.csv` / `h10_walkforward_results.csv` / `h10_strategy_returns.csv` | raw outputs |
| `beige_book_pull_v6.py` + `beige_book_patch_v7.py` | final scraper |
