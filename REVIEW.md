# REVIEW.md -- Milestone: event-study framework core + H11 event generator

Per the standing workflow: this is the handoff document for external
(GitHub-based) review of this milestone. Written before push, from the
actual commit(s) about to go up.

## What changed

New generic package `event_study/`:
- `schemas.py` -- the `Event` contract every hypothesis's event generator
  must produce, plus `UniverseRecord`, `ControlMatchResult`,
  `CostAdjustedReturn` for the other pipeline stages.
- `identifiers.py` -- point-in-time CIK<->ticker resolution, with explicit
  recycled-ticker conflict detection (`TickerConflict`,
  `find_conflicts()`).
- `universe.py` -- parametrized cap/liquidity/listing filter
  (`UniverseConfig`, `build_universe`, `attrition_summary`).
- `matched_control.py` -- size-quintile / sector matched-control benchmark
  construction, with an optional extra grouping key for H12's momentum
  stratification.
- `cost_model.py` -- pluggable ADV-bucketed cost schedules
  (`H11_LIQUIDITY_SCALED_SCHEDULE`, `H12_FLAT_SCHEDULE`) through one shared
  `apply_cost_model()` function.
- `diagnostics.py` -- `run_gate()` (the mechanical enforcement of "never
  continue past a failed validation"), `StageRunLog`, attrition tables.
- `event_study_runner.py` -- thin orchestrator wiring stages 4-5 over a
  list of `Event`s.

New hypothesis-specific package `hypotheses/h11_pead/`:
- `config.py` -- H11's fixed parameters, each traced to a
  `H11_PREREGISTRATION.md` section.
- `event_generator.py` -- `compute_sue()`, `determine_known_at()`,
  `determine_entry_date()`, `build_event()`.

New connectors in `data_connectors/`:
- `sec_company_tickers.py`, `sec_financial_statement_datasets.py`,
  `sec_8k_item202.py` -- each split into a pure `parse_*` function (unit
  tested against fixture data) and a `fetch_*` function (real HTTP,
  untested here -- see Validation section).

New `backtests/h11_data_probe.py` -- the Phase 0 vertical-slice script.

New tests: `tests/test_event_study_schemas.py`,
`test_identifiers.py`, `test_universe.py`, `test_matched_control.py`,
`test_cost_model.py`, `test_diagnostics.py`,
`test_h11_event_generator.py`, `test_sec_connectors.py`,
`test_integration_vertical_slice.py`.

## Why it changed

This is the first implementation milestone following the design/
architecture phase closed by the prior commits (`6f5b166`, `f3c5aa3`,
`bfeb401`). Per `H11_IMPLEMENTATION_SPEC.md`, the goal was to build the
generic event-study framework core -- not a PEAD-specific backtest -- and
prove H11's event-generation logic slots into it through the `Event`
contract, per the "PEAD is the first client of the framework" mandate.

## New assumptions introduced

- **XBRL data source**: SEC's bulk Financial Statement Data Sets
  (`sec_financial_statement_datasets.py`) are used as primary, per the data
  availability review's recommendation, with per-CIK `companyfacts`/
  `submissions` calls reserved for audits -- not yet exercised in this
  milestone beyond the identifiers connector.
- **8-K Item 2.02 timestamp source**: the SEC submissions API's per-filing
  `items` field and `acceptanceDateTime`, rather than full-text search or
  document text-scanning. This is implemented against SEC's documented API
  shape but **has not been verified against a live response** -- flagged
  explicitly in `sec_8k_item202.py`'s docstring as needing confirmation on
  first real local run.
- **EPS tag priority**: `["EarningsPerShareDiluted",
  "EarningsPerShareBasicAndDiluted"]`, in that order. Reasonable per common
  XBRL practice, not yet validated against a real custom-tag fallback rate.

## New invariants introduced

- **`known_at > period_end`, enforced at `Event.__post_init__`, zero
  tolerance.** A violating `Event` cannot be constructed at all -- this
  moves the highest-priority check in the whole design (per
  `H11_IMPLEMENTATION_SPEC.md` section 4/8) from "a validation step run
  later" to "a condition that fails fast, at the moment of creation,
  everywhere in the codebase, including in future H12 code that imports
  this same `Event` class."
- **Cost schedules must be contiguous with no gaps or overlaps**,
  enforced at `CostSchedule.__post_init__` -- every ADV value must resolve
  to exactly one bucket, checked at schedule-construction time rather than
  discovered later as a silent `bucket_for()` failure on some input.

## Validation performed

- **155 tests pass** (49 pre-existing + 106 new), `python -m pytest tests/`.
- **A real bug was caught and fixed during this milestone**, not just
  avoided: `Event.__post_init__`'s first implementation compared a
  tz-aware `known_at` against a tz-naive `period_end` directly, which
  raises `TypeError` in pandas rather than doing the wrong thing silently
  -- still a bug (it would have crashed on the very first real event), now
  fixed by normalizing both to naive timestamps before comparison, with a
  regression test (`test_known_at_one_second_after_period_end_is_valid`)
  added specifically to guard against it recurring.
- **Integration test** (`test_integration_vertical_slice.py`) runs ~30
  synthetically-generated events, produced through the real
  `compute_sue()` / `determine_known_at()` / `build_event()` functions
  (not hand-constructed `Event()` calls), through the real
  `run_matched_control_and_cost_stages()` orchestrator. This proves the
  pieces compose correctly; it does **not** validate against real SEC data
  or real point-in-time timestamps -- see Remaining Risks.
- **What was NOT validated in this milestone, and cannot be from this
  environment**: any `fetch_*` function against a live SEC endpoint. This
  sandbox cannot reach `data.sec.gov` or `www.sec.gov` (confirmed directly
  during the H11 data availability review -- only `pypi.org` and
  `github.com` resolve). `backtests/h11_data_probe.py` is written and
  syntax-checked but has never been run against real data. This is
  consistent with this project's standing pattern (FRED, 13F, yfinance
  pulls have always been local-execution-only) -- not a new limitation
  introduced here, but worth stating plainly rather than implying more
  confidence than is warranted.

## Remaining risks

1. **A genuine ambiguity in the frozen `H11_PREREGISTRATION.md` was found,
   not silently resolved.** Section 3 states "5 consecutive quarters" as
   the minimum XBRL history needed for the SUE formula's "8-quarter
   volatility window." Taken literally this doesn't add up -- a standard
   deviation needs at least two seasonal-difference observations (6
   quarters minimum), and the full 8-quarter window described needs up to
   12. This implementation uses an explicit, separately-named parameter
   (`H11Config.min_seasonal_diffs`, currently 4, requiring 8 quarters
   minimum) rather than reinterpreting "5 consecutive quarters" silently.
   **Recommend a formal pre-registration amendment resolving this before
   any real SUE value is computed against live data** -- this is exactly
   the kind of methodology-affecting ambiguity the standing workflow rule
   says shouldn't be resolved mid-implementation.
2. **8-K/A amendment handling is incomplete relative to the full
   pre-registration nuance.** `H11_PREREGISTRATION.md` section 4/8
   describes an edge case: if the original 8-K omitted Item 2.02 and a
   later amendment adds it, the amendment's timestamp should be used.
   `sec_8k_item202.py`'s current parser filters to `form == "8-K"` exactly,
   which correctly excludes amendments from ever *overriding* an original
   filing's timestamp, but does not yet implement the fallback-to-amendment
   case when no qualifying original exists. Flagged, not silently ignored;
   low expected frequency but not yet measured.
3. **The `sec_8k_item202.py` JSON-shape assumption is unverified against a
   live response** (see Validation section) -- first local run of
   `h11_data_probe.py` should specifically confirm this before trusting any
   further output from that connector.
4. **The integration test's synthetic universe is sparse enough that many
   events get an empty control group** (`control_n == 0`), correctly
   flagged via `thin_control_flag` rather than silently defaulting to
   zero -- but this is a real preview of a real risk: if the true 2015-2025
   universe's sector/quintile cells are thinner than assumed, a systematic
   pattern of thin control groups is a stated stop condition
   (`H11_IMPLEMENTATION_SPEC.md` section 4, stage 4) that hasn't been
   exercised against real universe density yet.
5. **`event_study_runner.py` has a real inefficiency**: it re-scans
   `events` with `next(e for e in events if e.event_id == ...)` inside a
   loop, which is O(n) per lookup. Fine at the ~30-event integration-test
   scale; worth an index/dict lookup before running this against the full
   30,000-60,000-event panel the data availability review estimates --
   noted here rather than silently deferred.

## Specific areas where external review should focus

1. **The `Event` contract (`event_study/schemas.py`)** -- this is the
   interface the entire "reusable framework" claim depends on. Worth
   checking whether the field list is actually sufficient for a
   structurally different hypothesis (H12's cluster events) without
   modification, or whether something H11-specific leaked into what's
   supposed to be a generic contract.
2. **The liquidity-scaled cost model (`event_study/cost_model.py`) and its
   bucket boundaries** -- these are asserted, not fit to data, and the
   decision rule in `H11_PREREGISTRATION.md` section 12 leans on them
   directly. Worth an independent sanity check against real small-cap
   spread data once available.
3. **The `known_at`/as-filed-XBRL point-in-time logic**
   (`event_study/schemas.py`'s invariant, `hypotheses/h11_pead/
   event_generator.py`'s `determine_known_at`/`determine_entry_date`) --
   this project's actual bug history (H10's release-date placeholder, the
   recycled BRKL ticker) is entirely in this category, not in statistical
   methodology. The tz-comparison bug caught during this milestone (see
   Validation) is a concrete instance of exactly this risk class,
   reinforcing why this area gets the most scrutiny.
4. **The SUE minimum-history ambiguity** (Remaining Risks item 1) --
   whether `min_seasonal_diffs = 4` is the right resolution, or whether a
   different value should go into a formal amendment.
