# H11 implementation spec — engineering design for a reusable event-study framework

This is not the pre-registration. `H11_PREREGISTRATION.md` fixes *what* is
being tested and the decision rule for interpreting the result; this
document fixes *how it gets built* — architecture, contracts, validation,
and failure handling. Nothing here may change the hypothesis, the decision
rule, or the trial count; anything here can change freely as engineering
judgment improves, without touching the frozen pre-registration.

## 0. Framing: this is not a PEAD backtest

The deliverable is a **canonical event-study framework** for this
repository. PEAD is the first hypothesis run through it. The test of good
architecture here isn't "does H11 produce a result" — it's **how little
H12 has to write.** H12 (`H12_PREREGISTRATION.md`) is structurally a
different event type (multi-insider Form 4 clusters instead of earnings
surprises) running through the *same* universe construction, point-in-time
discipline, matched-control logic, cost model, cross-validation, and
statistical testing. If the architecture is right, H12's own new code is
one event-generation module and one config file — everything downstream of
"here is a list of point-in-time-safe events" is untouched.

**Standing rule for the whole implementation phase, stated once here and
binding throughout:** never continue past a failed validation because "it
probably won't matter." Every stage below has explicit pass/fail gates. A
failed gate stops work. The response to a failed gate is either a fix
(engineering) or a written amendment to the pre-registration (research) —
never a silent continue.

---

## 1. Architecture overview

Nine stages, run in order. Stages 0–2 and 4–8 are **generic** — built once,
reused by every future event-driven hypothesis. Stage 3 is the only stage
that is hypothesis-specific by design.

```
[0] Raw data acquisition        (generic connectors, source-specific)
        |
[1] Identifier resolution       (generic: CIK <-> ticker, point-in-time)
        |
[2] Universe construction       (generic: cap/liquidity/listing filters, parametrized)
        |
[3] EVENT GENERATION            <-- HYPOTHESIS-SPECIFIC (H11: SUE + 8-K timestamp)
        |                           (H12 will replace only this stage)
[4] Matched-control construction (generic: size/sector/momentum-bucket benchmark)
        |
[5] Cost model application      (generic: pluggable cost schedule)
        |
[6] Cross-validation setup      (generic: cv.py, unmodified)
        |
[7] Statistical testing         (generic: stats.py, unmodified)
        |
[8] Diagnostics & reporting     (generic: standard diagnostic tables + writeup)
```

## 2. Module boundaries

| module | generic or H11-specific | reused by H12 without change? |
|---|---|---|
| `data_connectors/sec_financial_statement_datasets.py` | source connector | no — H12 needs a Form 4 connector instead, but sits in the same package alongside it |
| `data_connectors/sec_8k_item202.py` | source connector | **yes** — H12 also needs 8-K Item 2.02 timestamps, for its own earnings-exclusion filter (H12 §4.4) |
| `data_connectors/sec_company_tickers.py` | source connector | **yes** — identical identifier problem in both hypotheses |
| `event_study/identifiers.py` (CIK↔ticker, point-in-time) | generic | **yes**, unmodified |
| `event_study/universe.py` (cap/liquidity/listing filter) | generic, parametrized by config | **yes**, H12 passes its own thresholds ($50M–$2B, ADV floor) into the same function |
| `hypotheses/h11_pead/event_generator.py` | **H11-specific** | no — this is the module H12 replaces |
| `hypotheses/h11_pead/config.py` | H11-specific parameters | no — H12 gets its own config |
| `event_study/matched_control.py` | generic | **yes** — same size/sector-quintile logic H12 §6 already specifies reusing |
| `event_study/cost_model.py` | generic, pluggable schedule | **yes** — H12 supplies its own flat-50bps schedule instead of H11's ADV-bucketed one, same interface |
| `event_study/event_study_runner.py` (orchestrator) | generic | **yes**, unmodified — takes an event generator as a parameter |
| `event_study/diagnostics.py` | generic | **yes**, unmodified |
| `cv.py`, `stats.py`, `feature_store.py`, `costs.py` | already generic, pre-existing | **yes**, unmodified (as already stated in both pre-registrations) |

If, during implementation, something planned as generic turns out to need
H11-specific logic to work, that is exactly the kind of forced deviation
§5 of the workflow (amendment, not silent edit) applies to — but it also
means the architecture claim in this document was wrong and needs revising
before H12 starts, not after.

---

## 3. The event contract — the interface that makes reuse possible

Every event-generator module (H11's, later H12's) must emit records
conforming to this schema, and stages 4–8 depend on nothing else about
where the event came from:

| field | type | meaning |
|---|---|---|
| `event_id` | str | unique per event, hypothesis-prefixed (`h11_<cik>_<period_end>`) |
| `entity_id` | str | CIK, matching `PITFeatureStore`'s existing `entity_id` convention |
| `ticker` | str | point-in-time-resolved ticker, from `event_study/identifiers.py` |
| `known_at` | timestamp | when the event became public — **the only timestamp downstream stages are allowed to use for entry-timing logic** |
| `period_end` | date | the period the event describes (fiscal quarter for H11, transaction-date range for H12) |
| `market_cap` | float | at `known_at`, used by stage 4's quintile bucketing |
| `sic_code` | str | 2-digit, used by stage 4's sector bucketing |
| `adv_20d` | float | 20-day median dollar ADV as of the day before `known_at`, used by stage 5 |
| `signal_value` | float | the hypothesis's own sort variable (SUE for H11; not applicable in the same way for H12, which is binary cluster membership — nullable) |
| `event_source` | str | e.g. `"8k_item202"` vs `"10q_fallback"` for H11 — every hypothesis's coarser-precision fallback path must be labeled, never silently merged |
| `hypothesis_meta` | dict/JSON | anything hypothesis-specific that stages 4–8 don't need (H11: raw EPS values; H12: insider CIKs in the cluster) |

Stage 3 (event generation) is the *only* place this schema gets produced.
Stages 4–8 are written against this contract and this contract only — they
must never reach back into raw source data.

---

## 4. Stage-by-stage spec

### Stage 0 — Raw data acquisition

- **Inputs:** none (external SEC endpoints).
- **Outputs:** raw, unmodified snapshots — SEC Financial Statement Data Sets
  (per quarter, `num.txt`/`sub.txt`), 8-K Item 2.02 filing index, SEC
  `company_tickers.json` and `submissions` records.
- **Persisted as:** `data/raw/h11/{source}/{quarter_or_date}.{csv,json}`,
  one file per source per period, never overwritten — a re-pull writes a
  new dated file, matching this project's "outputs immutable, new filename
  for revisions" convention.
- **Validation:** row count per quarterly file within an order of magnitude
  of SEC's own published filing-volume figures (sanity floor, not a strict
  bound); every file has a recorded pull timestamp and SEC data vintage.
- **Expected volume:** ~44 quarterly files (2015–2025) from Financial
  Statement Data Sets, each covering *all* XBRL filers, not just this
  project's universe — filtering happens in stage 2, not here.
- **Failure condition → stop:** a quarter fails to download, or downloads
  with materially fewer rows than the SEC's own published counts for that
  period. Do not substitute, interpolate, or skip a quarter silently.

### Stage 1 — Identifier resolution

- **Inputs:** stage 0's `company_tickers.json` / `submissions` snapshots.
- **Outputs:** a point-in-time CIK↔ticker table: `(cik, ticker, valid_from,
  valid_to, company_name, sic_code)`.
- **Validation:** every ticker that appears more than once across the table
  is checked for the H10-style recycled-ticker failure mode (same ticker,
  different CIK, overlapping-looking date ranges) — flagged, not
  auto-resolved.
- **Expected volume:** roughly one row per CIK per ticker-history segment;
  the vast majority of CIKs have exactly one segment (no ticker change).
- **Failure condition → stop:** any ticker maps to more than one CIK for
  an overlapping date range with no resolution rule — this is exactly the
  project's highest-risk mapping category (`H11_data_availability_review.md`
  §5); it gets a human-reviewed exception list, not a heuristic guess.

### Stage 2 — Universe construction

- **Inputs:** stage 0 raw financial data, stage 1 identifiers, price panel.
- **Outputs:** `(cik, ticker, date, market_cap, sic_code, adv_20d,
  qualifies)` — one row per candidate firm-quarter.
- **Validation:** attrition table (raw firm-quarters → after listing filter
  → after cap-band filter → after XBRL-history filter), each step's count
  logged.
- **Expected volume:** per `H11_data_availability_review.md` §4, roughly
  90,000–110,000 firm-quarter slots before filtering, narrowing toward the
  30,000–60,000 range after the cap-band and history filters — **this is a
  planning estimate, not a target to engineer toward; report the real
  number, don't adjust filters to hit the estimate.**
- **Failure condition → stop:** final universe count falls materially below
  30,000 firm-quarters *and* the shortfall isn't explained by a specific,
  identifiable cause (e.g., worse-than-expected XBRL coverage). An
  unexplained shortfall is treated as a bug per the standing rule, not
  absorbed and continued past.

### Stage 3 — Event generation (H11-specific)

- **Inputs:** stage 2 universe, stage 0 raw EPS/8-K data.
- **Outputs:** records conforming to the §3 event contract.
- **Validation:**
  - as-filed vs. restated EPS audit (≥30 sampled events, pre-registration
    §13.1)
  - look-ahead audit: `known_at` strictly later than `period_end` for
    **100% of records, zero tolerance** (this is not a sampled check like
    the others — it's a hard invariant, same as `feature_store.py`'s own
    design guarantee)
  - custom-tag fallback rate and 8-K-fallback rate, both reported
    (pre-registration §13.4, §13.5)
- **Expected volume:** subset of stage 2's universe that has a resolvable
  EPS surprise and a qualifying event date — expect measurable attrition
  from custom-tag and fallback losses, magnitude unknown until measured.
- **Failure condition → stop:** any record with `known_at <= period_end`
  (hard invariant violation — this is the single most important gate in
  the whole pipeline, given it's this design's core claimed contribution
  over standard practice).

### Stage 4 — Matched-control construction

- **Inputs:** stage 3 events, stage 2 universe (for control-group
  candidates).
- **Outputs:** `(event_id, control_return, control_n, quintile, sic_code)`.
- **Validation:** `control_n` (number of firms in the matched-control
  group) reported per event — a control group with too few firms is
  flagged, not silently used (an implicit minimum, e.g. control_n ≥ 5,
  else the event is excluded and counted in attrition, not dropped
  invisibly).
- **Expected volume:** one control-return row per stage-3 event.
- **Failure condition → stop:** a systematic pattern of thin control groups
  (e.g., >10% of events with control_n below the minimum) — indicates the
  quintile/sector bucketing is too fine for the universe size, an
  architecture problem to fix before trusting any downstream result.

### Stage 5 — Cost model application

- **Inputs:** stage 3 events (for `adv_20d`), stage 4 returns.
- **Outputs:** `(event_id, raw_return, control_adjusted_return, adv_bucket,
  cost_bps, net_return)`.
- **Validation:** distribution of events across ADV buckets reported before
  any net-return number is interpreted (pre-registration §9's whole point).
- **Failure condition → stop:** none specific beyond upstream — this stage
  is close to pure arithmetic given a correct schedule, so a failure here
  usually means a bug in the schedule lookup, not a data problem, and gets
  caught by unit tests (§8) rather than a runtime gate.

### Stage 6 — Cross-validation setup

- **Inputs:** stage 5 output panel.
- **Outputs:** train/test fold assignments via `cv.py`'s existing
  `walk_forward_splits` / `PurgedKFold`.
- **Validation:** reuse of the existing purge/embargo test suite
  (`tests/test_cv.py`) — no train/test overlap, verified the same way every
  prior hypothesis in this project has verified it.
- **Failure condition → stop:** any overlap detected — this would be a
  regression in already-tested infrastructure, treated as a hard bug.

### Stage 7 — Statistical testing

- **Inputs:** stage 6 folds, stage 5 panel.
- **Outputs:** the four test results specified in pre-registration §11,
  BH-FDR-adjusted, deflated Sharpe at 82 cumulative trials.
- **Validation:** results computed only after stages 0–6 have each passed
  their own gates — this stage does not run at all if any upstream gate is
  outstanding.
- **Failure condition → stop:** not applicable in the usual sense — this
  stage's "failure" is a null result, which is a valid, reportable outcome,
  not a bug. The only true failure here is a coding error in the test
  itself, caught by unit tests (§8).

### Stage 8 — Diagnostics & reporting

- **Inputs:** every diagnostic artifact from stages 0–7.
- **Outputs:** `results/H11_results.md` (writeup, same format as
  `H10_beige_book_results.md`), plus every diagnostic table published
  alongside it, not just the ones supporting the conclusion — including a
  full attrition funnel from stage 0's raw row count down to stage 7's
  final tested sample.

---

## 5. Persisted intermediate datasets

| stage | file(s) | format |
|---|---|---|
| 0 | `data/raw/h11/{source}/{period}.csv` | raw, unmodified |
| 1 | `data/h11_identifiers.csv` | cik, ticker, valid_from, valid_to |
| 2 | `data/h11_universe.csv` | firm-quarter panel with qualifies flag |
| 3 | `data/h11_events.csv` | the event-contract table (§3) |
| 4 | `data/h11_matched_control.csv` | per-event control returns |
| 5 | `data/h11_panel_net_returns.csv` | final test-ready panel |
| — | `data/h11_diagnostics/*.csv` | one file per diagnostic table (fallback rates, attrition, control_n distribution, ADV bucket distribution) |

Every stage's output is a real file, not an in-memory handoff — this is
what makes each stage independently testable and restartable, per the
implementation goal stated in this request. Re-running stage *N* only
requires stage *N-1*'s output file to exist, nothing upstream of that.

---

## 6. Logging requirements

Every stage emits a structured run record (JSON) alongside its output file:
`{stage, input_row_count, output_row_count, elapsed_seconds, validation_
results: {check_name: pass/fail/value}, timestamp, git_commit_hash}`. This
is the mechanism that makes "never continue past a failed validation"
enforceable in practice rather than aspirational — a stage that fails a
validation writes `pass: false` and the orchestrator halts before invoking
the next stage, rather than relying on a human noticing.

---

## 7. Performance expectations

Rough targets, not measured facts — to be corrected once stage 0 actually
runs:

- Stage 0 (bulk SEC downloads): dominated by network time, not compute;
  SEC Financial Statement Data Sets are a few hundred MB per quarter
  zipped, ~44 quarters — expect this to be the slowest stage in wall-clock
  time, budget for it to run unattended, not interactively.
- Stages 1–5: pandas-scale operations on a dataset in the tens of
  thousands of rows — should run in minutes on a standard laptop, no
  distributed computing needed, consistent with this project's $0-budget,
  single-machine constraint throughout.
- Stage 6–7: reuses already-tested, already-performant existing modules.

If any stage materially exceeds these expectations, that's worth noting in
the postmortem (Phase 9, "result reporting," of `IMPLEMENTATION_CHECKLIST.md`)
as a data-volume-underestimation finding, not silently optimized away.

---

## 8. Test strategy

- **Unit tests**, one file per new generic module, matching the existing
  `tests/` convention (`test_cv.py`, `test_stats.py`, `test_costs.py`,
  `test_feature_store.py`):
  - `test_identifiers.py` — point-in-time ticker resolution correctness,
    including a synthetic recycled-ticker case (regression test for the
    H10 BRKL failure mode)
  - `test_universe.py` — filter logic, boundary conditions on cap/ADV
    thresholds
  - `test_matched_control.py` — quintile/sector bucketing correctness,
    thin-control-group flagging
  - `test_cost_model.py` — ADV-bucket lookup correctness, boundary values
- **Property-based / invariant tests:** `known_at > period_end` for 100% of
  event records — this is the single highest-value test in the whole
  suite given §4's stage-3 discussion, and should be written before any
  other stage-3 test.
- **Integration test:** the Phase-0 vertical slice
  (`backtests/h11_data_probe.py`, ~100 events end-to-end) becomes a
  permanent fixture in `tests/`, not a throwaway script — it's the cheapest
  possible full-pipeline regression test for every future hypothesis that
  reuses this architecture.
- **Regression tests inherited, not rewritten:** `tests/test_cv.py` and
  `tests/test_stats.py` already cover stages 6–7; no new tests needed there
  unless this implementation reveals a gap.

---

## 9. Reproducibility requirements

- **Raw data snapshots are immutable once pulled**, timestamped and dated
  in their filename, never re-downloaded-in-place — matches this project's
  existing convention (H10's committed Beige Book panel, for the same
  reason: the source can change or become unavailable later).
- **Deterministic random seeds** for every block-bootstrap resampling step,
  recorded in the run log (§6) so a result can be exactly reproduced.
- **Pinned dependencies** — any new library goes into `requirements.txt`
  with a pinned version, consistent with existing project practice.
- **SEC data vintage recorded explicitly.** As-filed data should be stable
  by construction (that's the point of pulling as-filed rather than a
  vendor's restated series), but the pull date is still recorded, since
  SEC's own bulk file structure or coverage could change between the
  implementation date and any future re-run.

---

## 10. Final output artifacts

- `results/H11_results.md` — the writeup, same convention as
  `H10_beige_book_results.md` / `H10b_beige_book_locality_results.md`.
- `data/h11_*.csv` — the committed intermediate datasets (§5), for the
  same reason H10's data is committed: reproducibility once a free source
  becomes harder to re-pull.
- `data/h11_diagnostics/*.csv` — every diagnostic table, published in full.
- Updated `README.md` results table, once — and only once — pipeline
  Stage 7 (statistical testing, §4 above) has actually run and the
  pre-registration's decision rule has been applied.
- The H11-vs-H10/H10b postmortem requested separately, written after this
  stage, per the standing request to extract cumulative-learning value
  regardless of outcome.

---

## 11. What this buys H12

If this spec is followed as written, H12's own implementation should
consist of: a Form 4 connector (stage 0), a cluster-detection event
generator producing records in the §3 contract (stage 3), and a config
file. Stages 1, 2, 4, 5 (with a different cost schedule), 6, 7, and 8 are
called, not rewritten. That is the concrete, falsifiable test of whether
"reusable research infrastructure" was actually achieved here, rather than
just asserted — H12's own implementation effort is the evidence either way.
