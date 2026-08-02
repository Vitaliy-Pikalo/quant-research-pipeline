# REVIEW.md -- Milestone: fix 8-K acceptance_datetime UTC-to-Eastern bug

Per the standing workflow: this is the handoff document for external
(GitHub-based) review of this milestone. Supersedes the prior milestone's
`REVIEW.md` (preserved in git history at `50e3871`).

**Scope note, stated up front:** this is a point-in-time integrity bug
fix, not a research or measurement-definition change. It is deliberately
NOT bundled with the EPS-tag investigation triggered by the same probe run
-- that investigation (whether to widen `EPS_TAG_PRIORITY` to include
`EarningsPerShareBasic`) touches `H11_PREREGISTRATION.md` section 5's
"diluted EPS from continuing operations" construct and is being handled
separately, via an analysis document before any amendment is even
proposed. This commit changes nothing about which records get extracted or
which tags are accepted.

## What changed

The second real H11 Phase 0 probe run (3 CIKs, 11 trailing quarters)
surfaced a real bug in `events.csv`: the event built from Powell
Industries' 8-K Item 2.02 (`event_source=8k_item202`) carried
`known_at = 2022-08-02 21:14:34+00:00` (UTC), while Lakeland's and Culp's
10-Q-fallback events correctly carried a `-04:00` (Eastern) offset. Root
cause: `sec_8k_item202.py`'s `parse_submission_filings_for_item_202()`
parsed SEC's `acceptanceDateTime` (always UTC, "Z"-suffixed) and left it
in UTC, never converting to US/Eastern the way `h11_data_probe.py`'s
10-Q-fallback path already did for `filed`. `H11_PREREGISTRATION.md`
section 6's entry rule (same-day close if `known_at` is before 4pm ET,
next trading day's close otherwise) and `event_study.schemas.Event`'s own
docstring both require `known_at` to be interpretable in Eastern wall-clock
time.

- **`data_connectors/sec_8k_item202.py`**: `acceptance_datetime` is now
  parsed with `utc=True` (forcing tz-aware UTC interpretation even if a
  given record's string happened to lack an explicit offset) and then
  `.tz_convert("US/Eastern")` -- the identical pattern already used
  elsewhere in this project for the same purpose. One line changed. Module
  docstring's HONESTY FLAG updated to record that the JSON-shape assumption
  has now been verified live (it held), separately from this timezone bug
  (which didn't).
- **`tests/test_sec_connectors.py`**: new `TestAcceptanceDatetimeTimezoneConversion`
  class, 5 tests, covering exactly what was asked: the raw UTC input, the
  Eastern conversion's correctness including a DST boundary (summer EDT
  UTC-4 vs. winter EST UTC-5, so the fix isn't accidentally only correct
  half the year), and the actual 4pm-ET entry-date decision once a real
  parser output flows into `determine_entry_date()` -- including a test
  using the specific UTC hour range (16:00-20:00 UTC) where the pre-fix bug
  would have silently produced the WRONG entry date, not just a
  differently-formatted correct one.

## Why it changed

Per explicit instruction: this is a point-in-time integrity bug, not a
research decision, and does not wait for a broader milestone. "The
existing issue is exactly the type of subtle bug the PIT framework is
designed to catch."

## New assumptions introduced

None beyond what already existed. SEC's `acceptanceDateTime` was already
assumed to always be UTC (documented in EDGAR's own format); this fix acts
on that existing assumption rather than introducing a new one.

## New invariants introduced

None new. This restores an existing, already-documented requirement
(`known_at` must be Eastern-interpretable) that one of the two `known_at`
sources had silently failed to satisfy.

## Validation performed

- **215 tests pass** (`python -m pytest tests/`), up from 210.
- The fix was verified against the exact real value that surfaced the bug
  (`2022-08-02T21:14:34.000Z`, Powell Industries' real 8-K accession time)
  as one of the five regression test cases, not just a synthetic example.
- A dedicated test (`test_utc_hour_in_the_bug_risk_zone_is_now_handled_correctly`)
  targets the specific failure mode: a UTC hour between 16:00 and 20:00
  reads as "after 4pm" if misinterpreted as already-Eastern, but is
  actually before the Eastern cutoff once correctly converted -- this is
  the range where the pre-fix bug would have silently produced a wrong
  entry date (not a crash, not an obviously-wrong value), which is exactly
  why it wasn't caught by the two existing fixture-based test files before
  a real probe run surfaced it in actual output data.

## Remaining risks

Unchanged by this fix (carried forward from the prior milestone):

1. 8-K/A amendment fallback (original omits Item 2.02, amendment adds it)
   still not implemented.
2. CIK -> ticker resolution in the probe is still current-ticker-only, not
   point-in-time.
3. Whether `EPS_TAG_PRIORITY` should be widened to include
   `EarningsPerShareBasic` is unresolved -- explicitly not addressed by
   this milestone, being handled separately via
   `docs/H11_EPS_TAG_ANALYSIS.md` before any amendment is proposed.
4. The `_STANDARD_TAXONOMY_PREFIXES` completeness (namespace-based custom-
   tag rate) is unverified against SEC's full taxonomy list.
5. The duplicate-submissions-endpoint-per-CIK pattern is still visible in
   telemetry but not fixed.

## Specific areas where external review should focus

1. **The regression test coverage itself** -- whether the five
   `TestAcceptanceDatetimeTimezoneConversion` cases actually pin down the
   bug's real-world consequence (the wrong `entry_date`) rather than only
   the surface-level timestamp formatting, since the latter alone wouldn't
   have caught this class of bug if it recurred elsewhere.
2. **Whether any other `known_at` source in this codebase has the same
   latent UTC-vs-Eastern gap** -- this fix addresses the 8-K path
   specifically because that's where it was found; worth an explicit check
   that the 10-Q-fallback path (and any future primary-source additions)
   apply the same `tz_convert` discipline consistently rather than by
   convention.
