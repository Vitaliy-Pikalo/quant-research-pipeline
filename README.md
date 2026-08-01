# quant research pipeline

a from-scratch implementation of a statistically rigorous research pipeline for testing market inefficiency hypotheses, plus three real hypotheses run end to end against real data. built solo, on a $0 budget, using only free/public data sources.

**disclaimer:** this is educational and research work, not investment advice. nothing here is a trading recommendation. references to specific managers (Berkshire Hathaway, Renaissance Technologies) are based entirely on their public SEC 13F filings and are used only to test a published academic theory about information disclosure lags, not as commentary on their investment quality.

## tldr

three hypotheses tested through a purged cross validation / walk forward / multiple testing correction pipeline. all three came back statistically non significant once confounds and selection bias were controlled for. writeups in [`results/session_summary_v2.md`](results/session_summary_v2.md) (H8, H9) and [`results/H10_beige_book_results.md`](results/H10_beige_book_results.md) (H10).

| hypothesis | theory | result |
|---|---|---|
| H9 FX carry (UIP violation) | high rate currencies drift stronger than forward rates imply | not supported, pooled IC = -0.0125 (p=0.073) across 5 currencies |
| H8 13F institutional copycat investing | disclosed positions of low turnover managers retain informational value after the 45 day SEC reporting lag | not supported net of market, raw return "edge" was market beta |
| H10 Beige Book district sentiment | district level Fed tone leads that district's regional banks, excess of the regional bank sector | not supported. primary spec IC = 0.015 (p=0.56), 0 of 12 districts survive FDR. one secondary spec survived FDR and a block bootstrap, then failed split half replication and fell to DSR = 0.18 at the honest 75 trial count |

the three results are directly comparable: all use the same `cv.py` / `stats.py` / `costs.py`, and the deflated Sharpe trial count is carried cumulatively across the whole project (46 from H9, 6 from H8, 23 from H10) rather than reset per hypothesis.

## why this exists

most retail backtests silently leak information: look ahead bias from mis timestamped features, no purge/embargo around cross validation folds, no correction for testing dozens of ideas before reporting the one that "worked." this project implements the standard institutional fixes for each of those problems, then uses them honestly, including reporting negative results instead of only publishing the wins.

## running the tests

```bash
pip install -r requirements.txt
pytest
```

49 tests across `cv.py`, `stats.py`, `feature_store.py`, and `costs.py`. these aren't smoke tests, they check actual correctness properties: purge/embargo windows never overlap train and test, the point-in-time feature store never leaks a future value, benjamini-hochberg is provably more lenient than bonferroni on correlated p-values, and so on.

writing these caught a real bug: `deflated_sharpe_ratio` was subtracting a z-score-scale term directly from a raw Sharpe-ratio-scale term, a unit mismatch that made the correction wildly too punitive (it was flattening a genuinely strong, low-noise signal to DSR=0.0 at only 20 trials). fixed by scaling the expected-max-SR term by the Sharpe ratio's own standard deviation, per the actual Bailey & Lopez de Prado (2014) formula. the two hypothesis backtests in `results/` were re-checked after the fix, neither of their negative conclusions changed (both were already failing on raw significance and walk-forward stability, DSR was corroborating evidence, not the deciding one), but the demo's own reported DSR numbers are now materially different and more defensible.

## transaction costs

every return reported in the original H8/H9 backtests was gross. `costs.py` applies a documented bps-based cost model (20bps round-trip for equities assuming full quarterly turnover, 4bps for FX majors) and `backtests/run_h8_net_of_costs_backtest.py` reruns H8 net of costs. neither conclusion flips: Berkshire's already-negative excess return gets more negative, Renaissance's marginal +0.87% (already not significant) shrinks to +0.67%, still not significant. costs make the "no" more airtight, they don't manufacture one.

## structure

```
cv.py                    purged k-fold, combinatorial purged CV, walk-forward splits
stats.py                 deflated sharpe ratio, probability of backtest overfitting,
                          benjamini-hochberg FDR, harvey-liu-zhu threshold
regime.py                gaussian HMM + bayesian online changepoint detection
ensemble.py              out-of-fold stacking, meta-labeling
feature_store.py         point-in-time feature store (known_at vs period_end)
demo.py                  end-to-end smoke test on synthetic data, run this first
data_connectors/         FRED, wikipedia pageviews, and SEC EDGAR 13F pull scripts
backtests/                real backtests run against real data (FX carry, 13F copycat,
                          Beige Book district sentiment) plus their data pull scripts
data/                    committed datasets for H10, including the scraped Beige Book
                          sentiment panel and the audited regional bank price panel
archive/                 abandoned data source attempts, kept for transparency
results/                 full writeups, hypothesis dossier, and priority ranking
```

## the H10 data is committed on purpose

`data/` contains real datasets, which is unusual for a repo like this. two reasons, both learned the hard way:

- **the Beige Book panel takes ~10 minutes of polite scraping** across five different page layouts the Fed has used since 2010. `backtests/beige_book_pull_v6.py` regenerates it, but nobody should have to.
- **the price panel is no longer reproducible.** Four of the original 36 constituents delisted during the sample (BHLB, NYCB, SNV, CMA) and yfinance will not serve them. One ticker, BRKL, has since been *recycled* onto an unrelated instrument, so a naive re-pull today silently returns 18 rows of the wrong company. `data/district_constituent_report.csv` records exactly what was recovered, what was rejected, and why.

## scraping notes (H10)

The Beige Book scraper went through six iterations. Four of the failures would have produced a plausible *result* rather than an error, which is the reason this is documented rather than quietly fixed:

- **release dates.** A release's URL stem is its *period* month, not its publication month: `202505` is the May 2025 book, published 4 June 2025. An early version fell back to a `YYYY-MM-01` placeholder, measuring forward returns from roughly five weeks before the information was public. Fixed by taking the date from the `BeigeBook_YYYYMMDD.pdf` filename each release links. Validated by the fact that all 131 release dates land on a Wednesday, which is the Beige Book's publication convention.
- **boilerplate contamination.** The 2024+ template puts each district on its own page. Scoring those pages whole pulled ~850 words of identical site navigation into every sentiment score: word counts ran 1496 vs 640 elsewhere and polarity variance dropped ~40%. That is a structural break at the exact date the Fed changed its template, and a district-relative z-score reads it as a real, simultaneous, cross-district sentiment shift. Every era now uses one extraction rule: start at the district's own heading tag, stop at the footer.

## quickstart

```bash
pip install -r requirements.txt
python demo.py
```

`demo.py` runs the full stack on synthetic data and proves each component works: it correctly isolates one true signal from 49 noise decoys, and the deflated sharpe ratio correctly drops from 0.97 (assuming 1 trial) to 0.33 (correcting for 50 trials), reflecting real but reduced confidence once selection bias is priced in.

to run the real backtests, you need your own free API keys and normal internet access (this was originally built in a network restricted sandbox, so the connector scripts are meant to be run locally):

```bash
export FRED_API_KEY=...   # free, instant: https://fred.stlouisfed.org/docs/api/api_key.html
python data_connectors/fred_connector.py --series DGS3MO DEXUSEU --start 2010-01-01
python data_connectors/edgar_13f_connector.py --cik 0001067983
python backtests/yf_price_pull.py
```

then feed the resulting CSVs into a `PITFeatureStore` and point the backtest scripts at them.

H10 needs no API key and its data is committed, so it reproduces directly:

```bash
python backtests/run_beigebook_backtest.py   # main backtest, all 5 stages
python backtests/h10_stress_test.py          # 4 check stress test of the one FDR survivor
```

to rebuild H10's inputs from source instead (~10 min of scraping, plus a yfinance pull that
will no longer return the delisted constituents, see above):

```bash
python backtests/beige_book_pull_v6.py        # scrape + score, ~10 min
python backtests/beige_book_patch_v7.py       # 3 stragglers the main scraper misses
python backtests/regional_bank_price_pull.py  # yfinance, will fail on 4 delisted names
python backtests/delisted_backfill.py         # attempt recovery via successor listings
python backtests/build_clean_price_panel.py   # audit the recoveries, build the final panel
```

the last step is not bookkeeping. it is where each candidate successor series is accepted or
rejected on evidence: two are genuine renamings of the same listing, one is bit-identical to a
bank already in another district, one is a different company, and one ticker has been recycled
onto an unrelated instrument while still appearing to download successfully. reasoning is in the
script's docstring.

## key methodology decisions

- **purging + embargo**, not plain k-fold. any training row whose forward looking label window overlaps the test fold gets dropped, plus an embargo buffer after the fold, to stop serial correlation leaking signal across the train/test boundary.
- **deflated sharpe ratio**, every reported sharpe is checked against how many strategy variants were actually tried, not just the one that's being reported.
- **benjamini-hochberg FDR** across every batch of related hypothesis tests, not naive p < 0.05 on each test in isolation.
- **market adjusted returns**, the 13F backtest was rerun with SPY subtracted out after the raw version looked artificially strong. this is the single most important fix in the whole project: it flipped the conclusion entirely (see results).
- **cross sectional replication**, the FX carry test looked significant on EUR alone, then stopped being significant once extended to JPY/GBP/CHF/AUD. reported as not supported, since a result that only survives on one out of five currencies is noise, not signal.
- **cumulative trial counting across hypotheses**, not per backtest. the deflated Sharpe for H10 is computed against 75 trials, which includes the 46 spent on H9 and the 6 on H8. resetting the count for each new hypothesis is the most common way this correction gets quietly defeated.
- **dependence aware inference**, H10's one surviving specification used 42 day forward windows on releases spaced ~35 trading days apart, so the windows overlap and all 12 districts share each window. a block bootstrap resampling whole releases put the standard error 1.18x above the parametric one and moved p from 0.0058 to 0.0186. it then failed replication in half the sample.
- **no post hoc subsetting**, H10's most likely cause of a false negative is that large national banks (U.S. Bancorp, Truist) are mapped to districts by HQ and are not really district level bets. the obvious fix, rerunning on a "local banks only" subset, was deliberately not done, because a subset rule invented after seeing a null is a researcher degree of freedom and picking the one that rescues the hypothesis is precisely what this pipeline exists to prevent. it is written up as a pre registered follow up with an objective locality measure instead.

## known limitations

- berkshire's 13F history in this pull only goes back to 2016, not the full available range, due to pagination limits in the filing puller
- top 20 holdings by value is a simplification, renaissance technologies actually discloses roughly 3,500 positions per quarter
- 3 tickers (BK, LSXMK, PARA) have gaps in free price data and were excluded from the relevant quarters
- the FRED connector uses the standard (non vintage) API, fine for rarely revised series like interest rates, not safe for revised series like GDP without switching to ALFRED
- H10: 3 of 36 bank constituents are unrecoverable delistings, so Boston, Atlanta and Dallas run on 2 names instead of 3. the missing names are all acquisition targets, so their absence is not missing at random
- H10: 2 of 133 Beige Book releases (2011-03-02, 2015-03-04) could not be scraped
- H10: one constituent, FMBH (Mattoon, Illinois), sits near the 7th/8th Federal Reserve district boundary and its district assignment is unresolved
- H10: Loughran-McDonald is a bag of words dictionary with no negation handling, which is close to a worst case for the Beige Book's deliberately hedged prose ("modest", "slight", "little changed"). a weak measured signal may reflect a weak instrument rather than a weak effect

## license

MIT, see [LICENSE](LICENSE).
