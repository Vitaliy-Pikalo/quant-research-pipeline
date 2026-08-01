# H11 — pre-registration: point-in-time PEAD, modern sample, liquidity-scaled costs

**Written before any XBRL or 8-K data has been pulled and no return, IC,
Sharpe or p-value has been computed.** Locked on sign-off. Anything below
that changes afterward gets recorded as a deviation, in this file, with a
reason — same convention as `H10b_PREREGISTRATION.md`.

**Sequencing note:** this hypothesis now runs **before** the small-cap
insider-cluster hypothesis, which has been renumbered to **H12**
(`results/H12_PREREGISTRATION.md`). The reasoning for the swap is in
`results/H11_prioritization_review.md`; the reasoning for why this specific
test is worth running given decades of PEAD literature is in
`results/H11_rationale.md` and is not repeated in full here — read that
document first if the "why bother" question isn't already answered.

---

## 0. Why this, why now — short version

Not "because PEAD exists." Four hypotheses tested, zero supported, 78
cumulative trials, and this project is now pointed at live capital. Before
committing the Form-4-ingestion and entity-resolution effort H12 needs, this
test answers a cheaper, prior question: does *any* free-data equity anomaly
survive this project's specific evaluation framework — purged CV, cumulative
deflated Sharpe, BH-FDR, block-bootstrap inference — in a modern,
realistically-costed sample? Full rationale in `H11_rationale.md`.

---

## 1. Literature — condensed (full survey in `H11_rationale.md`)

- **Bernard & Thomas (1989, 1990)** — the original documentation of drift
  following earnings surprises; effect persists 60+ trading days.
- **Chordia, Goyal, Sadka, Sadka & Shivakumar (2009, "Liquidity and the
  Post-Earnings-Announcement Drift")** — the central dispute this design is
  built to engage. Monthly value-weighted long/short return: **0.04% in the
  most liquid quintile vs. 2.43% in the most illiquid quintile**; transaction
  costs consume **70–100%** of paper profits in aggregate. Read plainly:
  the effect is real and large exactly where it's hardest to trade.
- **Battalio & Mendenhall (2011); Li (2016)** — find PEAD survives realistic
  costs, contra Chordia et al. Both camps used a single flat cost
  assumption; neither reports a continuous cost-vs-liquidity curve.
- **Ng, Rusticus & Verdi (2008)** and related work — PEAD is stronger with
  low analyst coverage, low institutional ownership, high idiosyncratic
  volatility, and high transaction costs — the same capacity-constrained
  signature as everything else this project has tested since the Beige Book
  pivot.
- **McLean & Pontiff (2016)** — as in H12, anomalies decay 26% out-of-sample
  / 58% post-publication on average, less so in illiquid/high-idiosyncratic-
  risk names.

---

## 2. Hypothesis

**Small/micro-cap firms with the most positive as-filed seasonal earnings
surprise (SUE) will outperform, and firms with the most negative SUE will
underperform, a size- and sector-matched control portfolio over the
following 21 trading days — and this effect, net of a liquidity-scaled
transaction cost model, will be positive in at least some non-trivial
segment of the liquidity spectrum tested.**

Directional: predicted sign is **positive** for the long/short spread.

The hypothesis is not merely "PEAD exists" — it is specifically that the
effect (a) survives in a **2015–2025** sample using **as-filed, not
restated,** financial data, and (b) survives **somewhere identifiable** on a
continuous liquidity curve, rather than being asserted or denied by a single
flat cost number chosen in advance.

---

## 3. Universe

| rule | value | rationale |
|---|---|---|
| listing | NYSE, NYSE American, or Nasdaq primary listing | avoids OTC data-quality problems, matches H12 |
| market cap | $50M – $2B at time of event | small/micro-cap band, matches H12 for cross-hypothesis comparability |
| liquidity | **no floor — treated as a continuous stratifying variable, not a filter** (§9) | this is the design's central methodological choice: excluding illiquid names up front would beg the exact question (does it survive there) this test exists to answer |
| XBRL history | ≥5 consecutive quarters of diluted EPS on file, as-filed | minimum needed to compute a seasonal SUE with an 8-quarter volatility window and at least one 4-quarter lag |
| sample period | 2015-01-01 to 2025-12-31 | full mandatory-XBRL era; starts after essentially all load-bearing literature's samples end |

Universe is re-evaluated at each event date (same survivorship-safe
construction as H12 §3): a firm must meet the cap/listing/XBRL-history rules
as of the event, not as of some fixed starting date.

---

## 4. Event definition

An event fires for issuer *i* on the date its earnings announcement becomes
public, defined as:

1. **Primary source: the accession timestamp of an 8-K filing with Item
   2.02** ("Results of Operations and Financial Condition") filed within 5
   calendar days **before** the corresponding 10-Q or 10-K. This is the
   actual public earnings-release moment for the large majority of modern
   filers (post-Reg FD, most companies furnish results via press release/8-K
   well before the more detailed 10-Q/10-K follows).
2. **Fallback: the 10-Q/10-K's own accession timestamp**, used only if no
   qualifying 8-K Item 2.02 exists within that window — some smaller
   reporting companies file irregularly or skip a standalone earnings 8-K.
   **Every fallback event is flagged in a dedicated column and reported
   separately** (§13), not silently pooled with primary-source events, since
   it represents materially coarser point-in-time precision.
3. Quarterly events only (10-Q-linked); annual-report-only (10-K, no
   preceding quarterly filing that fiscal year) events are excluded, to keep
   the SUE construction's seasonal lag consistent.

---

## 5. Surprise measure

**Primary: seasonal-random-walk standardized unexpected earnings (SUE),
as-filed.**

```
SUE(i, t) = [ EPS(i, t) - EPS(i, t-4) ] / std( EPS(i, t) - EPS(i, t-4) )
```

using diluted EPS from continuing operations, computed over the trailing 8
quarters of available history. **`EPS(i, t)` is the value as originally
tagged in issuer *i*'s own XBRL instance document for that quarter's filing
— not a vendor's subsequently restated series.** This is the design's core
point-in-time contribution: a company that later restates a prior quarter's
earnings does not retroactively change what SUE would have been computed at
the time, because the as-filed value is pulled directly, per-filing, from
`data.sec.gov/api/xbrl/companyfacts/CIK##########.json` (free, no key,
official SEC endpoint).

**Secondary/robustness (declared, not primary): 3-day announcement-window
cumulative abnormal return** (day −1 to day +1 relative to the event date in
§4), the classic alternative operationalization of "surprise" used when SUE
is unavailable or to check SUE isn't the only thing carrying the effect.
This uses only price data already in the pipeline's scope — no new data
source.

No consensus-estimate data (analyst forecasts) is used anywhere in this
design, which fully removes the "consensus-estimate gap" flagged against
the dossier's original H2 in `zero_budget_priority_ranking.md`.

---

## 6. Point-in-time rule

Two timestamps, same discipline as every prior hypothesis in this project:

- `period_end` = the fiscal quarter the EPS value describes
- `known_at` = the §4 event timestamp (8-K Item 2.02 accession time, or the
  10-Q/10-K accession time on fallback)

**Entry:** closing price on the first trading day on which `known_at` has
already occurred by 4:00pm ET (same-day close if filed before 4:00pm ET,
next trading day's close otherwise) — identical convention to H8/H10/H12.

**Exit:** closing price 21 trading days after entry (primary); a 60-trading-
day exit is a declared secondary test (§11, test 2), matching Bernard &
Thomas's original longer drift window, not searched over.

`PITFeatureStore.write()` stores `known_at` as the event timestamp and
`period_end` as the fiscal quarter, exactly matching its existing schema —
no modification needed, same as H12 §5's use of the store.

---

## 7. Benchmark and return construction

Event-firm return minus an equal-weighted **matched control portfolio**:
all non-event firms in the same market-cap quintile (relative to the full
universe on that date) and same 2-digit SIC sector, with no qualifying
earnings event of their own in the same 21-trading-day window. This nets out
size and sector without needing a momentum stratification (unlike H12,
momentum is not an obvious confound here — SUE is itself close to a
momentum-adjacent measure by construction, and over-stratifying would start
starving cells of observations for no clear benefit).

Secondary benchmark, reported alongside: excess return over IWM, for
comparability with this project's other small-cap-adjacent tests.

Primary statistical test: **pooled rank-IC** between SUE and matched-control-
adjusted forward return (continuous, no decile threshold — same "no
threshold" philosophy as H10b §6). Strategy-level test (§11, test 4): top-
decile-minus-bottom-decile SUE portfolio, for direct comparability with the
classic literature's convention.

---

## 8. Controls

| confound | handling |
|---|---|
| market cap | matched-control quintile (§7) |
| sector | matched-control 2-digit SIC (§7) |
| market beta | proxied by the size/sector match; strategy-level beta to IWM reported explicitly |
| momentum | not separately stratified (see §7 rationale); reported as a breakdown by prior-6-month return tercile for transparency, not built into the primary construction |
| liquidity | **the design's primary stratifying variable, not a control to net out** (§9) |
| corporate actions | split-adjusted prices only; events within 10 trading days of an announced M&A/spinoff excluded (a merger announcement can trigger simultaneous unusual earnings-adjacent filings unrelated to a normal surprise) |
| fallback-source events | flagged and reported as a separate row (§4.2), never silently pooled |

---

## 9. Liquidity-scaled transaction cost model — the design's core methodological contribution

Rather than asserting a single flat round-trip bps figure (as H8/H10 used
20bps and H12 uses 50bps), net returns are computed against a **pre-
registered, monotonic, ADV-bucketed cost schedule**, fixed now, before any
return is observed:

| 20-day median dollar ADV | assumed round-trip cost (bps) |
|---|---|
| < $500K | 150 |
| $500K – $2M | 80 |
| $2M – $10M | 40 |
| > $10M | 20 |

This schedule is a documented, monotonically-decreasing-in-liquidity
assumption consistent with the general shape of costs reported in the
market-impact literature (costs scale inversely with liquidity; Chordia et
al. themselves report exactly this pattern, just without publishing a
reusable schedule) — **it is not fit to this dataset.** The primary output
of §11 test 4 is net return **by ADV bucket**, which is what directly
answers the Chordia-et-al-vs-Battalio-Mendenhall dispute empirically instead
of by assumption: if the effect is positive net of costs only in the top
bucket, that supports Chordia et al.; if it survives into the illiquid
buckets even under this conservative schedule, that's a materially stronger
result than either side of the existing debate has shown for a modern
sample.

---

## 10. Bias checklist

- **Look-ahead bias.** The as-filed-EPS rule (§5) and event-timestamp rule
  (§6) are the two purpose-built defenses. Audited before any return is
  computed (§13).
- **Survivorship bias.** Universe re-evaluated per-event (§3), not fixed at
  the sample start.
- **Multiple testing.** Every test in §11 consumes trial count under BH-FDR
  and the cumulative deflated Sharpe count evaluated in §12.
- **Overlapping events / clustered errors.** Many firms announce earnings in
  the same 1–2 week windows each quarter — standard errors use a **block
  bootstrap resampling whole announcement weeks**, not individual firm-
  events, matching H10b/H12's dependence-aware inference convention.
- **Corporate actions.** Split-adjustment audited against the existing price
  panel; M&A-adjacent exclusion per §8.
- **Data quality specific to this design.** The as-filed-vs-restated
  distinction (§5) is audited directly, not assumed to work — see §13.

---

## 11. Complete test list

| # | test | detail |
|---|---|---|
| 1 | **primary**: pooled rank-IC, SUE vs. matched-control return, 21d | block-bootstrap p-value by announcement week |
| 2 | **secondary (declared)**: 60-trading-day holding period | matches Bernard & Thomas's original drift window; reported as robustness, not an alternative primary |
| 3 | **secondary (declared)**: 3-day announcement-CAR surprise measure in place of SUE | checks the effect isn't SUE-construction-specific |
| 4 | **strategy**: top-decile-minus-bottom-decile SUE portfolio, 21d hold, net of the §9 liquidity-scaled cost schedule, reported by ADV bucket, deflated Sharpe | uses `cv.py` walk-forward splits |

**Four new trials.** These run **before** H12's own four trials (per the
resequencing), so the cumulative project trial count becomes **78 + 4 = 82**
at the time this pre-registration's tests are evaluated. H12's trial count
and decision-rule threshold have been updated accordingly to run against
**86** cumulative trials once it follows this one — see the amendment in
`H12_PREREGISTRATION.md`.

No specification outside this list gets run — not on SUE window length, not
on holding period beyond the two declared values, not on market-cap band,
not on the cost schedule's bucket boundaries.

---

## 12. Decision rule — fixed in advance

H11 is **supported** only if all four hold, evaluated on test #1 (primary),
with test #4 required to establish tradeability:

1. primary pooled rank-IC is positive, and
2. its p-value clears a block bootstrap by announcement week (10,000
   resamples), and
3. the top-minus-bottom decile strategy's mean return is positive **net of
   the §9 liquidity-scaled cost schedule in at least one ADV bucket**, and
4. deflated Sharpe at **82 cumulative trials** exceeds 0.95, computed on
   whichever ADV bucket(s) clear criterion 3.

A result that clears (1) and (2) but fails (3) in every bucket is reported
as **"real but untradeable at any liquidity level tested"** — a distinct,
useful conclusion, directly resolving the Chordia-et-al side of the dispute
for this sample. A result that clears (3) only in the least liquid bucket is
reported as **"real, but the capacity is likely too small to matter for live
capital"** — also useful, and explicitly not rounded up to "supported"
without that caveat attached.

---

## 13. Pre-data checks

1. **As-filed audit.** For a random sample of ≥30 events involving a company
   known to have restated at least one quarter in its history (identifiable
   via XBRL's own amendment-flag metadata), verify the SUE calculation used
   the value as originally filed, not the amended one. This is the check
   that specifically validates this design's core claimed contribution over
   standard practice — if it fails, the "improved PIT handling" claim in
   `H11_rationale.md` is not actually true of the implementation and must be
   fixed before proceeding.
2. **Look-ahead audit.** Verify `known_at` (§6) is strictly later than the
   fiscal period it describes, and that no price data dated before
   `known_at` entered feature construction, for a random sample of ≥30
   events — same category of check as H12 §13.1.
3. **Power check.** Given the universe (§3) and 2015–2025 sample, count
   qualifying events with **no returns computed**. Expected to be
   substantially larger than H12's (every qualifying small-cap files
   quarterly, vs. H12's comparatively rare multi-insider clusters) — this is
   the whole basis for sequencing this test first. If the count comes in
   surprisingly low (e.g., XBRL coverage gaps for smaller filers turn out to
   be worse than expected), that is reported before the backtest runs, same
   standard as H12 §13.2.
4. **Fallback-rate check.** Report what fraction of events use the §4.2
   10-Q/10-K fallback rather than a direct 8-K Item 2.02. A high fallback
   rate would weaken the timestamp-precision claim in `H11_rationale.md` and
   is reported honestly regardless of what it shows.
5. **Custom-tag fallback rate check**, added following
   `H11_data_availability_review.md` §1/§6. Report what fraction of events
   resolve EPS via the standard `us-gaap:EarningsPerShareDiluted` tag versus
   a fallback in the tag-priority list versus an unresolvable custom
   extension (excluded from the sample, counted, and reported). Custom-tag
   usage is documented in the XBRL data-quality literature to concentrate in
   lower-quality, smaller filers — precisely this design's universe — so
   this rate is expected to be non-trivial and is reported as a data-quality
   table alongside the primary result, not folded silently into it.

---

## 14. Declared in advance — what will NOT be done

- No liquidity floor/filter — liquidity is a stratifying output variable
  (§9), not a screen. This is the one departure from H12's convention,
  deliberate and explained in §3.
- No SUE-window search (fixed at seasonal/4-quarter lag, 8-quarter
  volatility window, per §5's standard construction).
- No holding-period search beyond the two declared values (21d, 60d).
- No cost-schedule-bucket search — §9's boundaries are fixed now.
- No market-cap band search — $50M–$2B only, matching H12 for comparability.
- If the result is null, or real-but-untradeable, the response is to report
  it — not to reach for a fifth test.

---

## 15. Pipeline integration

**Reused as-is:** `cv.py` (walk-forward splits for test #4), `stats.py`
(`deflated_sharpe_ratio`, `benjamini_hochberg`,
`probability_of_backtest_overfitting`), `feature_store.py`
(`PITFeatureStore`, same schema as every prior hypothesis), `costs.py`
(`apply_transaction_costs` generalized to accept the §9 bucketed schedule
instead of a single flat bps figure — the one small, backward-compatible
extension this design needs, not a new module).

**New, minimal:** (1) a connector for the **SEC Financial Statement Data
Sets** (quarterly bulk `num.txt`/`sub.txt` archives, free, official, no
key) as the primary as-filed EPS source — added per the data-availability
review (`H11_data_availability_review.md` §1, §6), preferred over per-CIK
`companyfacts` calls for building the full panel because it's a single bulk
download per quarter rather than ~2,000+ individual API calls; per-CIK
`companyfacts`/`companyconcept` calls are retained as the tool for the
§13 audit spot-checks, (2) an 8-K Item 2.02 event-timestamp connector,
(3) the SUE calculation itself (a formula, not new infrastructure), (4) the
matched-control-portfolio builder — reusable, with minor modification, from
H12's §6 design (same size/sector-quintile logic, momentum stratification
dropped per §7).

---

## 16. Known risks, stated now

1. **The cost schedule (§9) is an assumption, however documented.** If real
   spreads in this universe don't follow that shape, the tradeability
   conclusion (§12.3) could be wrong in either direction. This is the same
   category of risk H12's 50bps figure carries, made more transparent here
   by testing across a curve instead of one number, but not eliminated.
2. **SUE is a purely mechanical earnings-based measure and may miss
   surprises the market actually reacted to** (e.g., guidance changes,
   non-GAAP metrics investors focus on more than GAAP diluted EPS). The §5.2
   CAR-based secondary measure exists specifically to check whether this
   matters.
3. **This cannot rescue a genuinely absent effect.** If modern, correctly-
   PIT-handled, realistically-costed PEAD in this universe carries no signal,
   better data handling will not create any — the same honest limitation
   every prior pre-registration in this project has stated.
4. **XBRL tagging inconsistency across smaller filers** is a real, known
   data-quality risk (smaller reporting companies have historically had
   higher XBRL tagging error rates than large caps) — §13.1's audit is
   designed to catch this, not assume it away.

---

## sign-off

- [ ] approved by: __________________  date: __________

*No XBRL or 8-K data has been pulled and no return has been computed at the
time of writing.*
