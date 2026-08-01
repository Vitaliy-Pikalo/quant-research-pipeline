# quant research session, final summary

date: 2026 07 31
budget: $0, free data only
scope: build a real research pipeline, then run two hypotheses from the dossier against actual market data, start to finish

## tldr

tested two hypotheses on real data through a purged CV / walk forward / BH FDR pipeline. both came back negative once i corrected for confounds and multiple testing. that's not a fail, that's the point. a clean honest "no" beats an overfit "yes" every time.

| hypothesis | theory | result |
|---|---|---|
| H9, FX carry (UIP violation) | high rate currencies drift stronger than forward rates imply | not supported. pooled IC = 0.0125 negative (p=0.073) across 5 currencies, naive strategy sharpe = 0.33 negative, sign flips every walk forward fold |
| H8, 13F copycat investing | low turnover managers' disclosed positions keep informational value after the 45 day SEC lag | not supported once you adjust for the market. raw return "edge" for both berkshire and rentec was just market beta. excess of SPY return is negative for berkshire (statistically significant, wrong direction) and not significant for rentec |

## what got built (reusable stuff)

`quant_pipeline/` is a working version of the pipeline from part 3 of the dossier:

- `cv.py`, purged kfold, combinatorial purged CV (caught and fixed a real bug here: naive purge/embargo on non contiguous fold combos wipes the whole training set), walk forward splits
- `stats.py`, deflated sharpe ratio (bailey and lopez de prado), probability of backtest overfitting, benjamini hochberg FDR, harvey liu zhu threshold
- `regime.py`, gaussian HMM plus bayesian online changepoint detection
- `ensemble.py`, out of fold stacking, meta labeling
- `feature_store.py`, point in time feature store, stops look ahead bias via known_at vs period_end
- `data_connectors/`, FRED, wikipedia pageviews, SEC EDGAR 13F pull scripts

all verified on synthetic data (`demo.py`). it correctly picks out one true signal from 49 noise decoys, deflated sharpe drops from 0.97 at 1 trial to 0.00 at 50 trials. that's the pipeline doing exactly what it's supposed to, killing false positives.

## H9, FX carry trade

data: FRED 3 month t bill / interbank rates (US, EU, JP, UK, CH, AU), 2013 to 2026, real forward FX returns.

design: rate differential (USD minus foreign, 45 day publication lag applied) as the signal for forward FX return, tested across 5 currencies, walk forward validated.

result: pooled IC = 0.0125 negative, p = 0.073, not significant. 4 of 5 currencies had the wrong sign for carry theory. walk forward IC flipped sign every single fold (0.03, 0.09, 0.03, 0.07, 0.06 alternating). naive long short strategy: sharpe 0.33 negative, it loses money. deflated sharpe after 46 cumulative trials this session: 0.00.

an earlier EUR only version had looked promising (IC 0.108, survived FDR, naive sharpe 0.84) but it didn't hold up once i extended to JPY/GBP/CHF/AUD. that's exactly the kind of single market false positive the multi currency plus deflated sharpe check is built to catch.

## H8, 13F institutional copycat investing

data: berkshire hathaway and renaissance technologies 13F filings, 2016 to 2026, real SEC EDGAR pulls, top 20 holdings by value each quarter, forward returns from filing date, SPY as the market benchmark.

design: theory (yan and zhang 2009) says low turnover managers' disclosed positions keep informational value after the 45 day reporting lag, high turnover managers' don't. tested raw return and excess of SPY return, t test vs zero, head to head, BH FDR across 6 tests, split sample check.

| manager | horizon | raw return | excess vs SPY | survives FDR? |
|---|---|---|---|---|
| berkshire | 120d | +3.20% (p=0.048) | 2.52% negative (p=0.007) | yes, but negative, wrong direction |
| rentec | 120d | +6.84% (p=0.015, survived FDR) | +0.87% (p=0.63) | no |

what it means: berkshire's raw return "edge" was just market beta, its top 20 rode the broader bull market and nothing more. once adjusted it actually underperforms the market by 2.5 points over 120 days, which is statistically significant but the opposite sign from what the copycat theory predicts. rentec's raw edge, which initially looked like the more theory consistent result, collapses to noise once adjusted. head to head berkshire vs rentec is no longer significant at any horizon.

## known limitations, flagged honestly, not fixed

- berkshire's 13F history only goes back to 2016 in this pull, not 2013, the filing puller didn't paginate SEC's full archive
- top 20 by value is a simplification of rentec's actual ~3,500 position book
- 3 tickers (BK, LSXMK, PARA) have no price data and got excluded from the relevant quarters
- the FRED connector uses the standard series, not the revised vintage one, that's fine for rate/FX data but would be a look ahead trap for revised series like GDP

## bottom line

two independently built, real data tested hypotheses, both run through purging, walk forward validation, and multiple testing correction, both came back negative. no headline alpha found today, but the pipeline itself is real, it catches its own false positives (shown on synthetic data and on the EUR only H9 near miss), and it's ready to reuse on the next hypothesis without rebuilding anything.
