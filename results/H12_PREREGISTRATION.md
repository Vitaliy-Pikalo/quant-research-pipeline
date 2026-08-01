# H12 — pre-registration: small-cap insider cluster buying

**Written before any Form 4 data has been pulled and no return, IC, Sharpe or
p-value has been computed.** Locked on sign-off. Anything below that changes
afterward gets recorded as a deviation, in this file, with a reason — same
convention as `H10b_PREREGISTRATION.md`.

**Renumbering note:** this hypothesis was originally drafted and pre-
registered as **H11**. A subsequent research-prioritization review
(`results/H11_prioritization_review.md`) compared it against 11 alternatives
and concluded that a refined post-earnings-announcement-drift (PEAD) test
should run first, on methodological grounds — larger sample, no new
hand-built entity mapping, near-drop-in pipeline fit, and a cheap read on
whether free-data equity anomalies survive this project's evaluation
framework at all before committing to Form 4 ingestion and entity
resolution. That PEAD test became **H11**; this hypothesis moved to **H12**.
Nothing in the design below changed — only the label and its place in the
queue. The original file this was copied from is preserved at
`results/H11_PREREGISTRATION.md` with a pointer to this one, per the
project's convention of not overwriting prior written artifacts.

**Separately, on the H-number convention itself:** this project's H-numbers
track *execution order*, not the dossier's canonical numbering — H10 in this
repo is the dossier's idea #20 (Beige Book), not the dossier's own "H10"
(merger arbitrage), and this hypothesis's H12 label likewise has no relation
to the dossier's own H12 (earnings-call tone).

---

## 0. Why this, why now

Four hypotheses tested (H9, H8, H10, H10b), zero supported, 78 cumulative
trials. H10b's null was the more informative kind — it ruled out a specific
mechanism (locality dilution) rather than just failing to find a pattern. The
open question, recorded in `README.md`, was whether to keep spending trials on
the Beige Book family (Option A: breadth expansion) or close it and start an
independent hypothesis (Option C).

This project is now being pointed at **live trading capital**, not just a
research portfolio. That changes the bar: a hypothesis needs a plausible
reason to keep working *after* being found, not just a p-value that clears a
threshold once. Beige Book district sentiment fails that test on inspection —
the Cleveland and Boston Federal Reserve Banks publish their own quantitative
district sentiment indices. If the source itself publishes the derived
signal, there is no informational edge left to find.

H12 is the pivot: **small-cap insider cluster buying**, chosen because its
persistence mechanism is structural rather than informational. The claim is
not "the market hasn't noticed insiders buying" — screener products
(2iq, InsiderArbitrage, OpenInsider) sell exactly that signal today. The claim
is that large capital is *structurally* prevented from arbitraging it away in
small/micro caps, because a fund managing meaningful AUM cannot deploy size
into a $200M–$2B name without moving the price or breaching capacity limits.
That mechanism doesn't require the signal to be secret, only that the capital
able to act on it stays small. This is the same logic H10b measured (effective
breadth) applied to a different axis (capital capacity instead of basket
weighting).

---

## 1. Literature survey

### 1.1 Foundational — insider trading predicts returns, concentrated in small firms

- **Seyhun (1986, 1988, 1998)** — earliest systematic evidence that insider
  purchases predict abnormal returns; profitability concentrated in smaller
  firms, where a single insider is more likely to possess a larger share of
  all information about the company.
- **Lakonishok & Lee (2001, "Are Insider Trades Informative?")** — the
  benchmark event study, ~20 years of every reported U.S. insider transaction
  (NYSE/AMEX/Nasdaq). Small-cap purchases delivered roughly **7.4% abnormal
  return over the following 12 months**; predictive power *increases* when
  multiple insiders buy simultaneously; sales carry little to no signal
  (routine liquidity/diversification motives dominate sales, which is why
  this design uses purchases only).

### 1.2 The routine/opportunistic split — most of the "insider signal" literature is really about filtering out noise

- **Cohen, Malloy & Pomorski (2012, "Decoding Inside Information," *Journal of
  Finance*)** — decomposes insider trades into "routine" (same calendar
  timing every year — 10b5-1 plans, compensation-linked, predictable) and
  "opportunistic" (no such pattern). Opportunistic-only portfolios earn
  **~82bps/month** value-weighted abnormal return; routine trades earn
  **~0**. This is the single most important methodological result in the
  literature for this design: naively pooling all Form 4 purchases dilutes a
  real signal with a large mechanical/routine component that carries none.

### 1.3 Cluster buying specifically — smaller literature, but directly on point

- **Alldredge & Cicero (2015, "Attentive Insider Trading," *Journal of
  Financial and Quantitative Analysis*)** and **Alldredge & Blank (2019, "Do
  Insiders Cluster Trades with Colleagues?," *Journal of Financial
  Research*)** — insiders at the same firm cluster trades around their
  colleagues', more so under high information asymmetry and low investor
  attention. Clustered purchases earn abnormal returns **>2% over the
  following month**, roughly double the return to isolated single-insider
  purchases over a comparable horizon in related work. Clustering itself is
  evidence of shared information, not just correlated noise.
- **Industry/practitioner evidence** (2iq Research, InsiderArbitrage) is
  directionally consistent (cluster buys outperform single-insider buys by a
  wide margin over 21–90 day horizons) but is not peer-reviewed and the exact
  figures aren't independently reproducible — treated as motivating, not load
  bearing.
- A **2025 microcap-specific study** (17,237 open-market purchases,
  1,343 issuers, $30M–$500M market cap, 2018–2024) found a gradient-boosting
  classifier achieves AUC 0.70 out-of-sample on 2024 data, and — importantly —
  that returns are **concentrated in trades disclosed after a >10% prior price
  decline** (mean CAR 6.3%). This is a warning as much as a finding: it may be
  partly a value/reversal effect wearing an insider-trading costume, not a
  pure information effect. Addressed directly in §7 and §11.

### 1.4 What's saturated vs. what's a genuine gap

**Saturated** (do not re-litigate, cite and move on):
insiders' purchases predict returns; the effect concentrates in small firms;
multiple simultaneous insiders carry more signal than one; routine
(10b5-1/compensation-timed) trades carry ~no signal and must be filtered out;
sales are much less informative than purchases.

**Genuinely thinner:**
1. Almost all of the load-bearing literature (Lakonishok & Lee, Cohen/Malloy/
   Pomorski, Alldredge & Cicero) uses samples ending well before 2015. Given
   McLean & Pontiff (2016, *Journal of Finance*) find published anomalies
   decay **26% out-of-sample and 58% post-publication** on average — but decay
   *less* in stocks with high idiosyncratic risk and low liquidity, i.e. the
   arbitrage-capital-can't-reach-it category — a modern (2015–2026),
   micro/small-cap-only replication with point-in-time discipline is not
   something the classic papers directly answer, and is the closest thing to
   a genuine gap here.
2. The cluster-buying papers establish that clustering is *correlated* with
   information, but do not consistently apply the routine/opportunistic
   filter (§1.2) *within* cluster events. A cluster of routine, calendar-timed
   purchases (several executives whose 10b5-1 windows opened the same week)
   looks identical to a cluster of independent, opportunistic buys in raw Form
   4 data — the literature doesn't cleanly separate "informed cluster" from
   "mechanical cluster." That distinction is the design's actual novelty
   claim (§2), and it is modest — a combination of two established filters,
   not a new mechanism.
3. Applying a purged/embargoed CV, deflated-Sharpe-against-cumulative-trials,
   BH-FDR stack to this literature is itself unusual — the academic papers use
   calendar-time portfolio methodology, not walk-forward validation, and none
   of them report a multiple-testing-corrected Sharpe against a running trial
   count. That doesn't create new alpha, but it is a meaningfully more honest
   test than the ones already published.

---

## 2. Hypothesis

**A small-cap firm where three or more distinct insiders make open-market
purchases within a short window, excluding routine/calendar-timed trades and
trades clustered around scheduled earnings announcements, will outperform a
size-, sector-, and momentum-matched control portfolio over the following 21
trading days.**

Directional: predicted sign is **positive**.

**Economic justification, stated precisely:** the mechanism is not "the
market hasn't seen this Form 4." It is (a) multiple insiders acting
independently and near-simultaneously is a stronger information signal than
one insider acting alone (§1.3), and (b) capital large enough to compress this
signal to zero cannot deploy meaningful size into $50M–$2B names without
moving the price or breaching mandate/capacity constraints (§0), so the
signal — even if visible — is not fully arbitraged by the capital that
dominates price formation in liquid large caps. McLean & Pontiff's finding
that anomalies persist longer specifically in high-idiosyncratic-risk,
low-liquidity names is direct empirical support for (b), not just intuition.

---

## 3. Universe selection — objective rules, fixed in advance

| rule | value | source |
|---|---|---|
| listing | primary listing on NYSE, NYSE American, or Nasdaq | avoids OTC/pink-sheet data-quality problems that sank prior mappings |
| market cap | $50M – $2B free-float market cap **at time of event** | standard small-cap band; anchors to Lakonishok & Lee's "small firm" tercile without going to sub-$50M nano-cap where execution cost dominates any signal |
| liquidity | 20-trading-day median dollar ADV ≥ $500k **as of the day before the event** | Amihud-style illiquidity floor; excludes names where a live position can't be entered/exited without material market impact |
| listed for full sample window | required (no partial-history names spliced in) | avoids the H10 delisting/recycled-ticker failure mode recurring in a name universe likely to have *more* delistings than regional banks, not fewer |
| sample period | 2015-01-01 to 2025-12-31 | starts after the bulk of the load-bearing literature's sample ends (§1.4), long enough for a meaningful event count, stops before the live/forward period |

**Universe is re-evaluated at each event date**, not fixed once at the start —
a firm must meet cap/liquidity/listing rules *as of the event*, which is
survivorship-safe by construction (a firm that later delists or degrades in
liquidity is excluded from later events, but earlier events involving that
firm are not deleted retroactively).

---

## 4. Event definition

An event fires for issuer *i* on date *t* (the date the cluster condition is
first satisfied — see §5 for what "date" means here) if, within a rolling
**5-trading-day window ending at *t***:

1. **≥3 distinct insiders** (by CIK, not by Form 4 filing count — one insider
   filing three times is one insider, not a cluster) file Form 4 transaction
   code **`P`** (open-market or private purchase) for issuer *i*, and
2. **net insider activity is non-negative** — no insider at the same firm
   files a code `S` (open-market sale) inside the same window that, in
   dollar terms, offsets more than 25% of the cluster's aggregate purchase
   value (this excludes clusters that are actually mixed signals — some
   insiders buying, others selling — which is a materially different, more
   ambiguous event than unanimous buying), and
3. **none of the ≥3 qualifying purchases is "routine"** under the
   Cohen-Malloy-Pomorski definition: a trade is routine if the same insider
   made an open-market purchase in the same fiscal-quarter-relative window
   (e.g. same 4 weeks of Q1) in at least 3 of the prior 5 years. Insiders with
   <3 years of trading history are treated as opportunistic by default
   (insufficient history to establish a routine pattern), matching CMP's own
   treatment of this edge case.
4. **excluded if the last qualifying filing's known_at falls within
   ±5 trading days of the issuer's next-or-most-recent scheduled earnings
   announcement** (from EDGAR 8-K Item 2.02, or the exchange's earnings
   calendar). This is a hard exclusion, not a control variable, for the
   primary spec — see §11 for why, and §9 for a declared secondary spec that
   relaxes this instead of excluding.

Only condition (4) is a threshold chosen without a specific literature value
to anchor it; §11 explains why 5 days and treats it explicitly as a declared,
non-tunable choice rather than something searched over.

---

## 5. Point-in-time rule — this is the section most prior bugs in this project would have broken

Two timestamps exist for every Form 4 transaction and they are **not the
same thing**:

- `period_end` = the transaction date printed on the form (when the insider
  actually bought)
- `known_at` = the EDGAR filing accession timestamp (when the form became
  publicly visible)

Sarbanes-Oxley §403 requires Form 4 filing within **2 business days** of the
transaction, but late filings are common and must be handled by the actual
filing timestamp, never assumed. **`known_at` is always the accession
timestamp, full stop — no exceptions for filings that look late or
suspicious; those get flagged in a data-quality report (§13), not silently
corrected.**

The cluster event's own `known_at` is the accession timestamp of **the
filing that completes condition (1) in §4** — i.e. the moment the third
qualifying insider's Form 4 becomes public, not the transaction date of any
of the three purchases, and not the date of the *first* purchase. This is the
single highest-risk look-ahead bias point in this design: a naive
implementation that groups by transaction date and trades from that date
would be using information (that a cluster occurred) before it was
publicly knowable. `PITFeatureStore.write()` stores `known_at` as this
completion timestamp and `period_end` as the transaction date range, exactly
matching its existing `known_at`/`period_end` two-timestamp design — no
schema change needed.

**Entry:** closing price on the first trading day on which the event's
`known_at` has already occurred by 4:00pm ET (same-day close if filed before
4:00pm ET on a trading day, next trading day's close otherwise). Same
convention as H10/H10b's "close of the first trading day after the release."

**Exit:** closing price 21 trading days after entry. No discretionary
stop-loss or take-profit — adding either would be a free parameter, the exact
failure mode H10b's §6 already ruled out for basket weighting.

---

## 6. Benchmark and return construction

Raw event-firm return is not the test statistic — per §1.4 point 3 and the
2025 microcap paper's warning about prior-decline-driven returns, the primary
metric must strip out size, sector, and momentum before it means anything.

For each event, build a **matched control portfolio**: all non-event firms in
the same market-cap quintile (relative to the full universe on that date),
same GICS-sector-equivalent (SEC SIC code, 2-digit), and same prior-6-month
return tercile, that had **no qualifying cluster-buy event of their own** in
the trailing 60 trading days. Event-firm return minus the equal-weighted
control portfolio's return over the same 21-day window is the primary
dependent variable. This directly nets out beta, sector, size, and momentum
in one construction rather than as post-hoc regression controls, and reuses
only data already in the pipeline's scope (price panel + SIC codes from
EDGAR company facts, both free).

**Secondary benchmark**, reported alongside but not the primary test: excess
return over IWM (Russell 2000 ETF), for direct comparability with H8/H10's
SPY/KRE-relative convention.

---

## 7. Controls — explicit, not implicit

| confound | how it's handled |
|---|---|
| earnings announcements | hard exclusion window in the primary event definition (§4.4); a secondary spec (§9) relaxes this to a regression control instead, to check the exclusion isn't hiding a real earnings-linked effect |
| momentum | matched-control portfolio is stratified by prior-6-month return tercile (§6) |
| market beta | matched-control portfolio is same market-cap quintile, which proxies beta closely at this size range; strategy-level beta to IWM reported explicitly as a check |
| sector effects | matched-control portfolio stratified by 2-digit SIC (§6) |
| liquidity | universe-level ADV floor (§3) plus liquidity tercile as a *reported* breakdown of results, not a further stratification (stratifying on 4 dimensions at once starts starving each cell of observations — see §14 power check) |
| market cap | universe-level band (§3) plus matched-control quintile (§6) |
| reversal / "buying the dip" | reported explicitly as a robustness cut: results split by whether the event followed a >10% 20-day price decline, per the 2025 microcap paper's finding. If the effect is concentrated entirely in post-decline events, that is reported honestly as evidence for a reversal explanation, not suppressed |

---

## 8. Bias sources — checklist, addressed before any data is touched

- **Look-ahead bias.** Addressed by the `known_at` = cluster-completion-filing
  timestamp rule (§5). This is the design's biggest look-ahead risk and gets
  its own audit step in §13.
- **Survivorship bias.** Universe re-evaluated per-event, not fixed at start
  (§3). Delisted names are not excluded from history, only from *future*
  eligibility once they delist — matching the H10 lesson that dropping a name
  entirely (rather than truncating its eligible window) deletes real,
  non-random information (the delistings weren't random — H10's were all
  acquisition targets).
- **Multiple testing.** Every specification run against real data — primary,
  each declared secondary (§9), the strategy backtest — consumes trial count
  under BH-FDR and the cumulative deflated Sharpe count (§15). No
  undeclared exploration.
- **Overlapping events / clustered errors.** A single firm can generate
  multiple cluster events with overlapping 21-day windows; the same calendar
  period can contain many firms' events simultaneously (systematic risk
  co-movement, e.g. a small-cap-wide rally). Standard errors use a **block
  bootstrap resampling whole event dates** (not individual firm-events),
  matching H10b's §8.2 approach, which is the dependence-aware inference this
  design needs given events cluster in time (small-cap insider buying is not
  uniformly distributed across the calendar — it clusters after broad
  sell-offs, which is itself a confound noted in §7).
- **Corporate actions.** Two distinct risks, handled separately:
  (a) stock splits/spin-offs can make raw share counts in Form 4 filings
  non-comparable across a split — resolve using split-adjusted price series
  only, audited against the price panel's own corporate-action adjustments;
  (b) **index reconstitution** (Russell 2000 annual rebalance in particular)
  can produce mechanical small-cap return patterns around the same
  cap-size band this universe lives in, unrelated to insider information —
  events within 10 trading days of the annual Russell reconstitution date are
  flagged and reported as a separate row, not silently pooled with the rest.
- **Data quality specific to Form 4.** Transaction code filtering is strict:
  only code `P` counts as a qualifying purchase. Codes `A` (grants), `M`
  (option exercises), `G` (gifts), and `F` (tax-withholding dispositions) are
  excluded from the purchase count entirely — pooling these with genuine
  open-market buys is a known way to manufacture a fake cluster out of
  routine equity-comp mechanics.

---

## 9. Complete test list — nothing outside this list gets run

| # | test | detail |
|---|---|---|
| 1 | **primary**: event return vs. matched control, ≥3-insider cluster | §4 event definition, §6 matched-control return, block-bootstrap p-value |
| 2 | **secondary (declared)**: ≥2-insider cluster | relaxes §4.1's threshold to the literature's minimum bound (Lakonishok & Lee's footnote definition); reported as robustness, not as an alternative primary, same convention as H10b §7.2 |
| 3 | **secondary (declared)**: earnings-window included, with earnings-proximity as a regression covariate instead of an exclusion | checks whether §4.4's hard exclusion is hiding or inflating the effect |
| 4 | **strategy**: long event-firms only (no short leg — small-cap borrow is often unavailable or expensive, and modeling a short leg here would need a borrow-cost assumption not yet in `costs.py`), 21-day hold, net of costs, deflated Sharpe | uses `cv.py` walk-forward splits, `costs.py` for net returns |

**Four new trials.** At the time this was first written, that meant a
cumulative count of 78 + 4 = 82. Following the resequencing described in the
renumbering note at the top of this file, H11 (PEAD, `H11_PREREGISTRATION.md`)
now runs first and consumes 4 trials of its own, so the cumulative count by
the time H12's tests are actually run is **78 + 4 (H11) + 4 (H12) = 86.**

No further specs — not on cluster size, not on window length, not on holding
period, not on market-cap band — get run inside this pre-registration. Any of
those become a separate, freshly pre-registered hypothesis (H12b-style) if
motivated *before* seeing H12's results, per §12.

---

## 10. Decision rule — fixed in advance

H12 is **supported** only if all four hold, evaluated on test #1 (primary):

1. matched-control-adjusted return is positive, and
2. its p-value clears a block bootstrap by event date (10,000 resamples), and
3. the long-only strategy's mean return (test #4) is positive **net of
   costs**, using a small-cap-specific cost assumption — **not** the 20bps
   used for the regional-bank basket in H10/H10b, since small-cap spreads are
   materially wider. Pre-registered at **50bps round-trip**, sourced from
   typical academic small-cap transaction cost estimates (e.g. Novy-Marx &
   Velikov and related market-impact literature put small-cap round-trip
   costs meaningfully above large-cap; 50bps is a middle-of-range, documented
   assumption, not fit to this data), and
4. deflated Sharpe at **86 cumulative trials** (78 + H11's 4 + H12's own 4 —
   see the renumbering note at the top of this file) exceeds 0.95.

Anything less is reported as not supported. A result that clears (1) and (2)
but fails (3) is reported explicitly as "real but not tradeable at this cost
assumption" — a materially different, more useful conclusion than a flat
"not supported," and directly relevant given this is meant for live capital.

---

## 11. Why the reversal/"buying the dip" risk gets its own section

The 2025 microcap paper (§1.3) found the *strongest* returns concentrated in
clusters following a >10% price decline. That is the single most likely way
this entire hypothesis fails to be what it claims: if the matched-control
portfolio (stratified by prior-6-month momentum tercile, §6) still shows the
effect concentrated in post-decline events, the honest interpretation is that
this is substantially a value/reversal signal that insiders happen to also be
buying into — informative about insiders' timing skill, perhaps, but not
evidence that *cluster buying itself* carries incremental information beyond
"the stock got cheap." §7's explicit reversal breakdown exists specifically
so this can't get buried in an aggregate positive number.

---

## 12. Declared in advance — what will NOT be done

- No cluster-size search beyond the two declared specs (≥2, ≥3). Not ≥4, ≥5.
- No window-length search. 5 trading days, as specified in §4, is fixed.
  Alternative windows (10, 20 days) are a separate future hypothesis if
  pursued, with their own trial count — not tested here even as "just a
  robustness check," because unlike the ≥2/≥3 cluster-size spec, there is no
  literature anchor pinning a specific alternative window, which makes it a
  free parameter rather than a principled robustness cut.
- No market-cap band search. $50M–$2B only. A sub-$50M microcap universe is
  a separate hypothesis (higher expected effect per §1.4, but materially
  worse execution feasibility — deserves its own pre-registration with its
  own capacity discussion, not a footnote here).
- No holding-period search. 21 trading days only, matching this project's
  existing convention from H10/H10b.
- No discretionary stop-loss/take-profit.
- No short leg (§9, test #4) without a pre-registered borrow-cost model.
- If the result is null or fails the cost test, the response is to report it
  — not to reach for a further fix and a fifth run, per the project's
  standing rule.

---

## 13. Pre-data checks — run and reported before any return is computed

Two audits happen **before** §9's tests are run, mirroring H10b's practice of
auditing the locality weights before trusting the null:

1. **Look-ahead audit.** For a random sample of ≥30 events, manually verify
   that `known_at` (cluster-completion timestamp) is strictly later than the
   transaction date of all three qualifying purchases, and that no price data
   dated before `known_at` was used in feature construction. This is the
   check most likely to catch the H5-style bug (release-date-as-placeholder)
   recurring in a new dataset.
2. **Power check.** Count qualifying events in the $50M–$2B universe,
   2015–2025, under the primary (≥3 insider) definition, with **no returns
   computed yet**. Given a plausible effect size in the 2–4% range (anchored
   to §1.3's cluster literature) and typical small-cap idiosyncratic return
   volatility, a rough power calculation needs on the order of 150–250 events
   for a reasonable chance of a statistically distinguishable result at this
   effect size. **If the count comes in materially below that, this is
   reported before the backtest is run, and the decision rule in §10 is
   re-examined rather than run against underpowered data** — this is
   H10b's effective-breadth lesson applied here: a small basket problem and
   a small event-count problem are the same failure mode wearing different
   clothes.

---

## 14. Pipeline integration — what's reused vs. what's new

**Reused as-is, no modification:**
- `cv.py` — `PurgedKFold`, `CombinatorialPurgedCV`, `walk_forward_splits` for
  the strategy backtest (test #4)
- `stats.py` — `deflated_sharpe_ratio`, `benjamini_hochberg`,
  `probability_of_backtest_overfitting`, `harvey_liu_zhu_threshold` as an
  optional cross-check
- `feature_store.py` — `PITFeatureStore`, using its existing `known_at`/
  `period_end` two-timestamp schema exactly as designed (§5); no schema
  change needed, this dataset is precisely the use case the store's docstring
  describes
- `costs.py` — `apply_transaction_costs`, `cost_breakeven_turnover`, with a
  new documented small-cap bps assumption (§10.3) alongside the existing
  20bps regional-bank one, not replacing it

**New, minimal:**
1. A Form 4 connector pulling SEC's official structured bulk data sets
   (`https://www.sec.gov/data/form345`, free, quarterly JSONL, no key) —
   analogous in scope to the existing `data_connectors/edgar_13f_connector.py`.
2. A cluster-detection function implementing §4's rules (distinct-insider
   count, net-activity filter, routine/opportunistic classification, earnings
   exclusion) — the one genuinely new piece of logic.
3. A matched-control-portfolio builder (§6) — size/sector/momentum bucketing
   and control-return calculation. The second genuinely new piece; everything
   else is either a direct data pull or a call into existing modules.
4. Market cap / ADV universe filter, sourced from EDGAR company facts +
   existing price panel — same category of work as H10's constituent
   filtering, not new infrastructure in kind.

No new statistical machinery. The two new pieces (cluster detector,
matched-control builder) are event/data-shape logic, not new validation or
inference code — which is what "minimal new infrastructure" should mean here.

---

## 15. Robustness and falsification checks

- **Split-half replication** (matching H10's own use of this check): first
  half vs. second half of the 2015–2025 sample tested separately. An effect
  that only survives in one half is reported as a near-miss, not supported —
  same standard applied to H10's `chg`/42-day near-miss.
- **Reversal breakdown** (§11): results split by prior-20-day return
  (declined >10% vs. not), reported regardless of outcome.
- **Placebo test**: run the identical pipeline on **sales** clusters (≥3
  insiders selling) instead of purchases. Literature (§1.1) predicts sales
  carry little signal; if the sales placebo shows a comparably strong effect
  to the purchase primary, that is evidence the whole pipeline is picking up
  something mechanical (e.g. a size/liquidity artifact in the matched-control
  construction) rather than an insider-information effect specifically.
- **Falsification target, stated now**: if the primary effect (test #1)
  disappears entirely once earnings-window exclusion is relaxed (test #3),
  that says the "effect" was PEAD relabeled as an insider-cluster effect —
  reported as such, explicitly, not folded into a vaguer "partially
  supported."

---

## 16. Known risks to this design, stated now

1. **Reversal confound is the single biggest threat to interpretation**
   (§11) — a real risk, not a formality, given it's the headline finding of
   the most recent (2025) paper in this exact universe.
2. **The routine/opportunistic filter (§4.3) is itself an estimated
   classification**, not ground truth — an insider with genuinely irregular
   but coincidentally-clustered-by-calendar trading history could be
   misclassified as routine. This is a known limitation of the Cohen-Malloy-
   Pomorski method itself, inherited here, not introduced by this design.
3. **Form 4 → issuer → CIK → ticker → price-panel matching is a sixth
   hand-built mapping** in this project's lineage (13F CUSIP map, H10's Fed
   district map, H10b's FDIC ticker map, and now this). Every one of the
   prior five contained at least one real error caught by an automated gate.
   The same gates (name-similarity refusal threshold, cross-check against an
   independent field, minimum-observations check) get built for this mapping
   before it's trusted, not after a plausible-looking result appears.
4. **Small-cap price and delisting data is likely to be worse than the
   regional-bank panel's, not better** — small caps delist, get acquired, or
   go dark far more often than regional banks did. Budget for this in
   advance rather than discovering it mid-backtest.
5. **This cannot rescue a genuinely absent effect.** If cluster buying in
   this universe and period carries no incremental information beyond size/
   sector/momentum, better matched-control construction will not create any.

---

## 17. Adversarial critique — read this as if it came from a quant researcher at AQR, Two Sigma, Citadel, or RenTech

Written to argue against the hypothesis, not for it.

**"You're describing a retail-crowded niche, not an undiscovered one."**
Cluster-buy alerts are a commercial product today (2iq, InsiderArbitrage,
Quiver Quant, OpenInsider). The information isn't just theoretically public,
it's actively marketed to retail. The capacity-constraint argument (§0)
explains why *large* funds ignore it, but says nothing about whether *other
small, nimble capital* — the exact size bracket this design is aimed at — has
already compressed the edge. This is a different, milder crowding risk than
Beige Book's (institutionally published vs. retail-productized), but it is
not zero, and the design has no way to measure how much of the historical
edge in the literature has already been arbed by this smaller pool of
capital since those papers' sample periods ended.

**"Your reversal control is necessary but might not be sufficient."**
Stratifying by prior-6-month return tercile controls for medium-term
momentum, but the 2025 paper's finding was about a *sharp, recent* (20-day)
decline — a different, faster-moving effect than a 6-month momentum
tercile will fully capture. A stock can be flat over 6 months and still have
dropped 15% in the last three weeks. §7's separate reversal breakdown
partially addresses this, but if the effect really is short-horizon reversal,
a 6-month momentum control won't remove it from the primary number — only
the explicit breakdown will show it, and that's reported as a secondary
table, not baked into the headline result.

**"Four insiders filing near-simultaneously might just mean the blackout
window opened, not that they agree on new information."** Corporate blackout
policies typically lift shortly after earnings — which §4.4 already excludes
— but many firms also lift blackouts on other fixed corporate calendar
events (secondary offering completions, fiscal year-end) that this design
does not screen for. The routine/opportunistic filter (§4.3) catches
insiders who personally have a *repeating annual pattern*, but would not
catch a *first-time* mechanical clustering driven by a corporate-calendar
event that isn't earnings. This is a real gap, not fully closed by the
current design — worth stating rather than implying §4 is airtight.

**"Capacity works both ways."** The thesis is that big funds can't scale
into this — true — but that same illiquidity means a live strategy sized
much beyond a few hundred thousand dollars per name will itself move prices
on entry and exit, especially exiting into a 21-day-later close that isn't
chosen for liquidity reasons. The backtest's assumed 50bps round-trip cost
(§10.3) is a documented average, not a guarantee for the specific illiquid
tail of this universe — a fund-sized version of this strategy is a
contradiction in terms, and this pre-registration should not be read as
scalable past a fairly modest capital base, whatever the statistical result.

**"You picked $50M–$2B and 5 trading days — why these and not neighboring
values?"** The market-cap band is anchored to the literature's small-firm
tercile and the liquidity floor (reasonably defensible). The 5-day cluster
window is the weakest-justified fixed choice in the whole document — §4
flags it as literature-adjacent but not literature-pinned. A hostile
reviewer is right to ask why not 3 days or 10; the honest answer is that no
single paper pins this exact value, and §12 already commits to treating
alternative windows as a separate future hypothesis rather than testing them
here — but that commitment is a process safeguard against p-hacking, not
evidence that 5 days is the *right* window.

**Bottom line, stated as a verdict rather than hedged:** this design is
methodologically sound and meaningfully more rigorous than the papers it's
built on. It is not obviously going to survive contact with live small-cap
transaction costs and a genuinely uncrowded-capital assumption that may not
hold. Worth running — the pre-data power check (§13) and the reversal
breakdown (§11) are cheap enough, relative to the four trials spent, to be
worth spending them to find out. It is not worth over-trusting a positive
result on the first pass; the reversal confound in particular means a clean
"supported" outcome on test #1 alone, without checking §11's breakdown,
should not be believed.

---

## sign-off

- [ ] approved by: __________________  date: __________

*No Form 4 data has been pulled and no return has been computed at the time of
writing.*
