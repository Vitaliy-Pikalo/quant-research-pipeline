# REVIEW.md -- Milestone: H11 data-integrity validation (amendment, parser fixtures, probe report)

Per the standing workflow: this is the handoff document for external
(GitHub-based) review of this milestone. Supersedes the previous
`REVIEW.md` (committed at `9aedf9f`, still readable in git history).

**Scope note, stated up front:** per explicit instruction, this milestone
is validation, not feature expansion. Nothing here tunes a parameter or
changes what H11 measures. Two things were fixed -- both were bugs in
error-handling/edge-case code paths discovered by testing, not
methodology or filter changes.

## What changed

- **`amendments/H11_AMENDMENT_001.md`** (new) -- resolves the "5 quarters
  vs. 8-quarter volatility window" arithmetic conflict in
  `H11_PREREGISTRATION.md` sections 3/5, flagged but left open in the
  prior milestone. `results/H11_PREREGISTRATION.md` itself is **untouched**
  -- the amendment is a separate document per the standing rule against
  silently editing a frozen pre-registration. Still pending explicit
  sign-off (checkbox unchecked); real SEC data collection under H11 does
  not proceed on the `min_seasonal_diffs` threshold specifically until
  that box is checked, per the amendment's own §6.

- **`tests/test_sec_parser_fixtures.py`** (new, 10 tests) -- five named,
  deterministic validation scenarios requested for this milestone: a
  normal 8-K Item 2.02 filing, a filer with no qualifying Item 2.02 (10-Q
  fallback), 8-K/A amendments in both directions (correctly-ignored and
  known-incomplete), standard XBRL EPS tags, and custom XBRL extension
  tags. One of these tests (`test_custom_tag_using_an_abbreviation_is_
  invisible_to_the_fallback_diagnostic`) surfaced a real, previously
  undocumented limitation -- see Validation performed.

- **`hypotheses/h11_pead/probe_report.py`** (new) + 
  **`tests/test_h11_probe_report.py`** (new, 8 tests) -- a pure,
  fixture-tested report-assembly module: `AttemptOutcome`,
  `ProbeDataQualityReport`, `build_probe_report()`. Produces every field
  requested for this milestone (companies attempted/resolved, filings
  retrieved, events identified, EPS values extracted, standard/custom tag
  rates, CIK-ticker resolution failures, per-stage attrition funnel) as
  markdown + JSON, with zero network dependency of its own.

- **`backtests/h11_data_probe.py`** (rewired) -- now calls
  `build_probe_report()` at the end of a run and writes `report.md` /
  `report.json` alongside the existing per-stage diagnostics. Individual
  CIK fetch failures (submission lookup, 8-K lookup) are now caught and
  counted rather than aborting the whole probe run.

- **`data_connectors/sec_8k_item202.py`** (bug fix) -- see Validation
  performed. One line changed (`.astype(str)` added before
  `.str.contains()`), plus an explanatory comment.

- **`tests/test_sec_connectors.py`** (regression test added) -- locks in
  the zero-recent-filings fix.

- **`tests/test_h11_data_probe_e2e.py`** (new, 5 tests) -- the first actual
  execution of `h11_data_probe.py`'s `probe()` function, end to end, with
  `fetch_submission` / `fetch_quarter` / `fetch_item_202_filings`
  monkeypatched to fixture data (no network). Not a substitute for a real
  local run against live SEC data, but closes the gap between "syntax-
  checked" and "never actually executed," which is where both bugs below
  were found.

## Why it changed

Directly per this milestone's four numbered requirements: resolve the
open pre-registration ambiguity via a proper amendment document, add
deterministic parser fixtures before trusting live data, upgrade the
probe script to produce a real data-quality report, and continue the
atomic-commit/REVIEW.md workflow. The architectural confirmation
(connectors -> event generators -> event contract -> generic framework ->
stats, generic framework hypothesis-agnostic) was checked against every
file touched this milestone and is unaffected -- `probe_report.py` lives
in `hypotheses/h11_pead/`, not `event_study/`, because it's a diagnostic
over H11-specific event-generation output, not generic pipeline
machinery.

## New assumptions introduced

- `H11Config.min_seasonal_diffs = 4` (8-quarter minimum history) is now
  backed by a written rationale (`H11_AMENDMENT_001.md`) instead of only a
  code comment -- but it is still an **unapproved** proposal pending the
  sign-off checkbox. No behavior changed; this is a documentation-status
  change, not a code change.
- The probe's CIK -> ticker "resolution" is explicitly documented (in
  `probe_report.py`'s `STANDARD_NOTES`, surfaced in every report) as a
  **current-ticker-only** proxy, not true point-in-time resolution --
  `event_study.identifiers.PointInTimeTickerHistory` exists and is
  fixture-tested, but building the historical valid_from/valid_to table it
  needs is out of scope for this probe and remains the highest-risk open
  item per `H11_data_availability_review.md` section 5.

## New invariants introduced

None. This milestone adds validation and reporting around existing
invariants (`known_at > period_end`, contiguous cost buckets); it does not
introduce new ones.

## Validation performed

- **179 tests pass** (155 prior + 24 new: 10 parser fixtures, 8 probe-report
  unit tests, 5 end-to-end dry-run tests, 1 connector regression test),
  `python -m pytest tests/`.
- **Two real bugs were caught and fixed while building the fixtures and
  the end-to-end dry run, not just avoided:**
  1. `backtests/h11_data_probe.py`'s error-handling fallback for a failed
     `fetch_item_202_filings()` call built an incomplete stub submission
     dict (missing `accessionNumber`, `filingDate`, `acceptanceDateTime`
     keys), which crashed `parse_submission_filings_for_item_202()` --
     meaning the exact code path meant to handle a fetch failure
     gracefully would itself have crashed the whole probe run on the
     first CIK that failed to resolve. Fixed by supplying all required
     parallel-array keys as empty lists.
  2. `data_connectors/sec_8k_item202.py`'s `parse_submission_filings_
     for_item_202()` raised `AttributeError: Can only use .str accessor
     with string values!` on a submission with zero recent filings --
     pandas infers an empty column as `float64`, not `object`/string, and
     `.str.contains()` rejects non-string dtypes. This is a real edge
     case (a genuinely new filer with no filing history yet, or exactly
     the fallback-stub case bug #1 above exercises) that no fixture with
     at least one real filing would ever surface. Fixed with `.astype(str)`
     before `.fillna("").str.contains(...)`; regression-tested directly in
     `test_sec_connectors.py` and indirectly via the end-to-end test.
  Both bugs were in error-handling / edge-case code, not in the
  methodology or the primary happy-path logic -- but both would have
  caused the probe script to crash on its first real run against any CIK
  with a lookup failure or sparse filing history, which is a realistic,
  not a hypothetical, occurrence at small-cap scale.
- **A third finding, not a crash but a measurement gap**: 
  `custom_tag_fallback_rate()`'s heuristic (`tag.str.contains(
  "EarningsPerShare", case=False)`) does not recognize custom tags that
  abbreviate to "EPS" instead of spelling out "EarningsPerShare" -- such
  tags are invisible to both the numerator and denominator of the
  diagnostic, meaning the reported custom-tag fallback rate is a **lower
  bound**, not an exact figure, wherever this naming pattern occurs.
  Locked in as a passing, explicitly-named test
  (`test_custom_tag_using_an_abbreviation_is_invisible_to_the_fallback_
  diagnostic`) rather than fixed, per this milestone's validation-only
  scope -- widening the heuristic is a code change that would need its
  own before/after validation, which is exactly the kind of scope
  creep this milestone is deliberately avoiding.
- **What still cannot be validated from this sandbox**: any `fetch_*`
  function against a live SEC endpoint. The end-to-end dry run
  (`test_h11_data_probe_e2e.py`) proves the orchestration logic is
  internally correct against realistically-shaped fixture data; it does
  not and cannot prove SEC's actual live response matches that shape. The
  first real local run of `h11_data_probe.py` is still the point at which
  `sec_8k_item202.py`'s HONESTY FLAG gets resolved one way or the other.

## Remaining risks

1. **`H11_AMENDMENT_001.md` is unsigned.** Per its own §6, this blocks
   real SEC data collection specifically on the minimum-history threshold
   until approved.
2. **8-K/A amendment fallback (original omits Item 2.02, amendment adds
   it) is still not implemented** -- explicitly re-confirmed as
   out-of-scope for this validation-only milestone
   (`test_sec_parser_fixtures.py::TestEightKAAmendmentCase`), carried
   forward from the prior milestone's REVIEW.md, not newly discovered.
3. **The custom-tag fallback-rate heuristic undercounts abbreviated tag
   names** (new finding, see Validation performed) -- the true custom-tag
   rate in real data could be higher than what `custom_tag_fallback_rate()`
   reports. Worth widening the heuristic before the section 13.5
   diagnostic is treated as final, but not before this milestone.
4. **The 8-K JSON-shape assumption remains unverified against live data**
   -- unchanged from the prior milestone, still the first thing to check
   on the first real local run.
5. **CIK -> ticker resolution in the probe is current-ticker-only**, not
   point-in-time -- explicitly flagged in every report's Notes section now
   (previously only in `H11_data_availability_review.md`), so this
   limitation surfaces automatically wherever the report is read, not only
   to a reader who already knows to look for it.

## Specific areas where external review should focus

1. **`amendments/H11_AMENDMENT_001.md`'s sample-size impact estimate**
   (§5) -- it's a desk estimate reasoned from the XBRL mandate's June 2011
   full-coverage date, not a measured count. Worth checking the reasoning
   holds before treating the "low-to-mid single-digit percentage" claim as
   more than a planning aid.
2. **Whether `min_seasonal_diffs = 4` is the right number at all** -- the
   amendment argues for it over both the literal 5-quarter floor and the
   full 12-quarter window, but the choice of exactly 4 (vs. 5, 6, or the
   full 8) is a judgment call, not a derived value. This is the actual
   decision the sign-off checkbox is gating.
3. **The two bugs fixed this milestone** (see Validation performed) --
   both were found by testing error-handling paths specifically, which
   raises the question of whether other error-handling branches in the
   connectors (there aren't many, but `fetch_quarter`'s network-error path
   is entirely untested even by the new end-to-end fixture, since it never
   simulates a `fetch_quarter` failure) deserve the same treatment before
   the real panel run.
4. **The custom-tag heuristic gap** -- worth an opinion on whether
   widening it before or after the full panel run is the better
   sequencing, given it only affects diagnostic reporting accuracy, not
   which records enter the sample.
