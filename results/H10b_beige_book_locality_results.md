# H10b — Beige Book district sentiment, locality-weighted constituents

date: 2026-07-31
budget: $0, free/public data only
status: **not supported**
pre-registration: `H10b_PREREGISTRATION.md`, signed off before any data was pulled

## tl;dr

H10 returned a null and named one flaw as the most likely cause of a **false**
negative: banks were assigned to Federal Reserve districts by headquarters, but
several constituents are national franchises whose returns have little to do
with their home district's economy. H10b repaired that, exactly as
pre-registered, using FDIC Summary of Deposits to weight each constituent by
the share of its deposits held in its own headquarters state.

The repair worked. The result did not change.

| | H10 | H10b |
|---|---|---|
| pooled IC (z-score, 21d, excess of KRE) | 0.0153 | **0.0108** |
| one-sided p | 0.28 | 0.34 |
| block bootstrap p | — | 0.72 |
| long/short net Sharpe | −0.238 | −0.067 |
| DSR at cumulative trials | 0.0004 (71) | **0.0035 (78)** |
| verdict | not supported | **not supported** |

All four pre-registered decision criteria were required. One was met.

**The more useful finding is why the fix changed nothing**, and it partially
falsifies the hypothesis I wrote down in H10.

## the fix was applied correctly

This matters, because a fix that silently failed to apply would produce a null
that looks identical to this one. Audited independently:

- locality scores span **0.125 to 1.000** with a 4.7x spread in the latest
  vintage. Rockland Trust and Frost Bank score 1.000 (single-state banks);
  U.S. Bank scores 0.118–0.229 across 28 states. The measure separates.
- **561 bank-years, complete**, no missing vintages, arithmetic verified against
  an independent recompute.
- weights genuinely differ from equal weighting: mean absolute daily basket
  difference of 1.3–27.5 bps depending on district.
- point-in-time rule verified: a July 2018 release uses the 2017 SOD vintage,
  an October 2018 release uses 2018.

Example weights (2025 vintage), showing the intended effect — U.S. Bancorp
down-weighted to 13% of Cleveland, Ameris up to 74% of Atlanta:

```
Cleveland      KEY=0.28  HBAN=0.35  FITB=0.24  USB=0.13
Atlanta        RF=0.26   ABCB=0.74
Richmond       TFC=0.25  UBSI=0.21  AUB=0.54
```

## why it didn't matter

The locality-weighted district baskets correlate with the equal-weighted ones
at **0.9817 to 0.9999**.

That is the whole explanation. The dilution hypothesis assumed that
down-weighting national banks would materially change what a district basket
measures. It doesn't — because the two-to-four regional banks inside a district
co-move so strongly with each other that reweighting them alters roughly 1–2%
of the basket's variance. A district's "local" bank and its "national" bank
still move together, because both are regional banks in the same rate and
credit environment.

So the H10 null was not primarily an artifact of constituent selection. That
was a reasonable hypothesis, it was worth one pre-registered test, and it is
now substantially ruled out.

## the district reassignments

Pre-registration §4 required district assignment to come from the FDIC record,
published before returns. Three constituents moved:

| ticker | was | now | reason |
|---|---|---|---|
| ONB | Chicago | St. Louis | Old National is chartered in Evansville; southern Indiana is the 8th district |
| FMBH | St. Louis | Chicago | Mattoon, Illinois falls in the 7th |
| USB | Minneapolis | Cleveland | U.S. Bank N.A. is chartered in Cincinnati, not at the holding company's Minneapolis address |

The FMBH move **resolves the unresolved flag from H10**, which could not
determine which side of the 7th/8th boundary Mattoon sat on. Deriving from
FDIC's own charter-district field rather than from state answers it, and
handles the other split states (Illinois, Pennsylvania, Missouri, Indiana, New
Jersey) that a state-level rule would have guessed at.

## results

**Test 1, primary.** Locality-weighted pooled IC = 0.0108, n = 1,464, one-sided
p = 0.339. Block bootstrap by release date (10,000 resamples) gives a 95% CI of
[−0.047, 0.071], p = 0.717. The confidence interval comfortably contains zero.

**Test 2, secondary.** Majority-local subset (locality ≥ 0.50, equal weighted):
IC = 0.0204, one-sided p = 0.218. All 12 districts retain at least one
qualifying constituent in every release, so no district drops out. Slightly
larger than the primary, still indistinguishable from noise.

**Test 3, strategy.** Long top-3 / short bottom-3 districts by z-score, 21-day
hold: +0.129% per release gross, hit rate 48.4%, t = 0.48 (p = 0.63), gross
Sharpe 0.122. Net of 20 bps round-trip it is **−0.071% per release**, Sharpe
−0.067. Deflated Sharpe 0.398 treating this as the only trial ever run; **0.0035
against the project's honest cumulative count of 78**.

**Walk-forward** ICs across five purged folds: −0.067, −0.042, +0.067, +0.054,
+0.043. Three of five positive, sign unstable. Reported, not part of the
decision rule.

## verdict against the pre-registered rule

| criterion | required | actual | met |
|---|---|---|---|
| 1. primary IC positive | > 0 | 0.0108 | yes |
| 2. survives block bootstrap | p < 0.05, CI excludes 0 | p = 0.717 | no |
| 3. net-of-cost mean return positive | > 0 | −0.071% | no |
| 4. DSR at 78 trials | > 0.95 | 0.0035 | no |

**Not supported.**

## what this leaves standing

Four hypotheses now, four negatives, one yardstick. What separates this one is
that it was a *diagnostic* null rather than another exploratory one: it was
designed to distinguish "no effect" from "broken instrument", and it came back
saying the instrument was less broken than claimed.

Remaining candidate explanations for the H10/H10b null, in the order I would
now rank them:

1. **The sentiment instrument.** Loughran-McDonald is a bag-of-words dictionary
   with no negation handling, applied to prose engineered to hedge ("modest",
   "slight", "little changed", "activity declined less than expected"). This is
   now the largest untested weakness, and unlike locality it has not been ruled
   out.
2. **Effective breadth is very low.** Measured 1/Σw², districts run from 1.56
   (Boston) to 3.34 (Cleveland) effective constituents. Several districts are
   close to single-stock bets, so idiosyncratic firm news swamps whatever
   district-level macro signal exists. This is the §10.3 risk, and it
   materialised.
3. **Sector-relative returns may simply not carry district macro information**
   over a 21-day horizon. Regional banks trade on rates, credit spreads and
   sector sentiment, all national. The district-specific component of a bank's
   return may be a small fraction of its variance regardless of measurement.
4. **There may be no effect.** The Beige Book is a public, widely-read document
   released at a scheduled time; that any residual district-level signal
   survives to be traded 21 days later is not the null hypothesis, it is the
   surprising claim.

## limitations carried forward

- Locality is HQ-**state** share, not share-of-deposits-inside-the-Fed-district.
  Fed district boundaries are county-level and published only as ArcGIS
  shapefiles; the state proxy was pre-registered with this weakness stated.
- 3 of 36 original constituents remain unrecoverable delistings (BRKL, SNV,
  CMA), so Boston, Atlanta and Dallas run on 2 names.
- 2 of 133 Beige Book releases could not be scraped.
- The FDIC ticker→institution mapping is a fourth hand-built mapping in this
  project. Three errors were caught in it during construction (Truist resolving
  to Bank of America on a max-assets rule, United Bankshares resolving to an
  unrelated Indiana thrift, and NYCB resolving to the pre-2022 Michigan
  Flagstar charter). All three were caught by automated checks rather than
  inspection, which is the only reason I trust the fourth mapping more than the
  previous three.

## files

| file | contents |
|---|---|
| `H10b_PREREGISTRATION.md` | the pre-registration, signed before data |
| `fdic_locality_pull.py` | FDIC SOD pull, locality table |
| `h10b_district_assign.py` | FDIC-derived district assignment |
| `run_h10b_backtest.py` | the single pre-registered run |
| `h10b_locality.csv` | 561 bank-years of locality scores |
| `h10b_district_assignment.csv` | assignment table incl. the 3 reassignments |
| `h10b_results.csv`, `h10b_strategy_returns.csv` | raw outputs |
