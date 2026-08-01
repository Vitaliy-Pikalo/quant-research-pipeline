# H10b — pre-registration

**Written before any H10b return, IC, Sharpe or p-value has been computed.**
Locked on sign-off. Anything below that changes afterwards gets recorded as a
deviation, in this file, with a reason.

---

## 1. Why there is a second run at all

H10 returned a null: district Beige Book tone showed no relationship to that
district's regional-bank basket (pooled IC 0.015, p=0.56, 0/12 districts
surviving FDR).

The H10 writeup identified one flaw as the most likely cause of a **false**
negative: banks were assigned to districts by headquarters location, but
several constituents are national franchises whose returns have little to do
with their home district's economy. U.S. Bancorp is a ~$600bn national bank
nominally representing Minneapolis; Truist is a national franchise nominally
representing Richmond. If a district's basket is dominated by banks that don't
actually earn their money in that district, any genuine district-level effect
is diluted toward zero by construction.

H10b tests the same hypothesis with that flaw repaired. It is not a new
hypothesis and does not get a fresh trial count.

An additional error was found while scoping this: **FDIC assigns U.S. Bank
N.A. to the Cleveland district**, because the bank subsidiary is chartered in
Cincinnati, while our map assigned USB to Minneapolis from the holding
company's address. This is independent of the locality question and is
addressed in §4.

## 2. Hypothesis (unchanged from H10)

A district whose Beige Book tone improves relative to its own recent history
will see that district's regional banks outperform the regional-bank sector
over the following weeks.

Directional: the predicted sign is **positive**.

## 3. What changes, and what does not

**Unchanged, carried over from H10 exactly:**

- sentiment panel `beige_book_sentiment_final.csv` (131 releases, 12 districts)
- feature: district polarity z-scored against its own trailing 8 releases
- horizon: 21 trading days
- benchmark: KRE
- entry: close of the first trading day after the 2:00 pm ET release
- `cv.py` / `stats.py` / `costs.py`, unmodified
- 20 bps round-trip at full turnover

**The only change is how constituents are weighted inside each district basket.**

## 4. Locality measure

For bank *i* in SOD vintage year *Y*:

```
L(i, Y) = (deposits in branches located in bank i's HQ state)
          -----------------------------------------------------
                  (bank i's total domestic deposits)
```

Source: FDIC Summary of Deposits, `https://api.fdic.gov/banks/sod`, free, no
API key. Branch-level `DEPSUMBR` summed by `STALPBR`, divided by the sum across
all branches.

`L` runs 0 to 1. A single-state community bank scores near 1.0. A national
franchise scores low.

**HQ state is taken from the FDIC record, not from our hand-built map.** This
also corrects the U.S. Bancorp problem in §1: district assignment for H10b is
derived from the FDIC institution's own state, and any constituent whose
FDIC-derived district disagrees with our hand-built assignment will be
**reassigned to the FDIC-derived one**, with every such change listed in the
results before any return is computed.

Why HQ-state share rather than the theoretically ideal
share-of-deposits-inside-the-Federal-Reserve-district: Fed district boundaries
are defined at county level and are only published as ArcGIS shapefiles. Taking
on a geospatial dependency for one filter is poor value. HQ-state share is a
coarser but fully objective proxy that targets the same thing. Its known
weakness is recorded in §9.

## 5. Point-in-time rule

SOD is measured as of **30 June** each year and published at the **end of
September**.

For a Beige Book release on date *t*, use SOD vintage year *Y* where *Y* is the
largest year satisfying **`t >= 1 October of Y`**.

So a release in July 2018 uses the 2017 vintage, not 2018 — the 2018 survey had
been *taken* by then but not published. This is deliberately conservative and
costs roughly one year of data freshness in exchange for no publication-lag
look-ahead. SOD covers 1994 onward, so every release in the sample is covered.

`L` is therefore time-varying: a bank that grows out of its home state has its
weight fall over the sample, as it should.

## 6. Basket construction

District *d*'s basket return on day *t*:

```
r(d, t) = sum_i [ w(i, t) * r(i, t) ]     over constituents i of district d
w(i, t) = L(i, Y(t)) / sum_j L(j, Y(t))   normalised within the district
```

**No threshold, no inclusion cut.** Constituents are weighted continuously by
locality. This is a deliberate choice: any binary cut (>50%? >60%? >75%?) is a
free parameter I could tune until the answer changed, and picking the cut that
rescues the hypothesis is precisely the failure this project exists to avoid.
Continuous weighting has no such knob.

Where a constituent has no price on a given date (late listings CUBI from
2012-03, MSBI from 2016-05; unrecoverable delistings BRKL, SNV, CMA), weights
renormalise across whatever is available that day.

## 7. Tests to be run — this is the complete list

| # | test | detail |
|---|---|---|
| 1 | **primary**: pooled IC, locality-weighted baskets | z-score feature, 21d, excess of KRE, Pearson, one-sided (predicted sign positive) |
| 2 | **secondary**: pooled IC, majority-local subset | binary filter L >= 0.50, the one non-arbitrary cut ("most of the bank's deposits are at home"). Reported as robustness, not as an alternative primary |
| 3 | **strategy**: long top-3 / short bottom-3 districts | 21d hold, net of 20 bps, deflated Sharpe |

**Three new trials. Cumulative project trial count becomes 75 + 3 = 78.**

Per-district tests are deliberately **not** repeated: H10 already spent 12
trials establishing that no individual district carries a signal, and rerunning
them buys 12 trials' worth of penalty for very little information.

## 8. Decision rule, fixed in advance

H10b is **supported** only if all four hold:

1. primary pooled IC is positive, and
2. its p-value clears a **block bootstrap by release date** (10,000 resamples,
   resampling whole releases to preserve serial and cross-sectional
   dependence), not just the parametric p-value, and
3. the long/short strategy's mean return is positive **net of costs**, and
4. deflated Sharpe at **78 cumulative trials** exceeds 0.95.

Anything less is reported as not supported. A result that is positive but fails
(2) or (4) is reported as a near-miss, in the same terms H10's `chg`/42d
specification was.

## 9. Declared in advance — what will NOT be done

- No threshold search. §6 has no threshold; §7 test 2 uses 0.50 and only 0.50.
- No horizon search. 21 days, as pre-specified. H10 already tested 5/21/42 and
  those trials are already paid for.
- No feature search. The z-score feature only. In particular the `chg` feature
  that produced H10's near-miss is **not** carried into H10b, because combining
  a spec selected on H10's data with a fix designed after seeing H10's null is
  double-dipping.
- No district subsetting, no period subsetting, no regime conditioning.
- If the result is null, the response is to report it, not to reach for a
  further fix and a fourth run.

## 10. Known risks to this design, stated now

1. **HQ-state share is a proxy, not the real thing.** A bank concentrated in a
   state that straddles two Fed districts is still potentially misassigned.
   This affects the two Illinois constituents (FMBH, MSBI) most directly, and
   FMBH's district assignment was already flagged as unresolved in H10.
2. **Ticker-to-FDIC matching is a new manual mapping**, the same risk category
   as the CUSIP map in H8 and the district map in H10, both of which contained
   errors. Every match will be verified against institution name, HQ state and
   total assets, and the full mapping published with the results before any
   return is computed.
3. **Weighting reduces effective breadth.** If one constituent dominates a
   district's weight, that district's basket becomes close to a single-stock
   bet, which raises idiosyncratic noise. Effective N per district
   (`1 / sum(w^2)`) will be reported alongside the results.
4. **This cannot rescue a genuinely absent effect.** If tone carries no
   information, better constituent weighting will not create any. A null here
   is considerably more informative than H10's null was, and that is the point
   of running it.

---

## sign-off

- [ ] approved by: __________________  date: __________

*No FDIC data has been pulled and no return has been computed at the time of
writing.*
