# REVIEW.md -- Milestone: H11 EPS tag analysis (real data, no production change)

Per the standing workflow: this is the handoff document for external
(GitHub-based) review of this milestone. Supersedes the prior milestone's
`REVIEW.md` (preserved in git history at `e7dedac`).

**Scope note, stated up front:** this milestone produces evidence only. It
does not modify `EPS_TAG_PRIORITY`, `extract_eps_records()`, or
`custom_tag_fallback_rate()` anywhere. No amendment has been drafted or
approved. Whether to widen the EPS definition to include `EarningsPerShareBasic`
remains an open, unresolved research-construct decision.

## What changed

The second real H11 Phase 0 probe run measured a 40.8% "custom-tag rate"
for EPS-like facts, raising the question of whether that reflects real
data-quality risk or is mostly a labeling artifact of `EarningsPerShareBasic`
(a standard `us-gaap` tag not currently in `EPS_TAG_PRIORITY`) being counted
as "custom."

- **`backtests/h11_eps_tag_analysis.py`** (added, committed at `1b0dceb`):
  read-only analysis script. Uses `extract_eps_records()`'s existing
  `tag_priority` override parameter to simulate a candidate expanded
  priority list against real data -- no change to the function or the
  production tag list. Outputs real tag distribution, a tag-by-tag
  classification (diluted / basic / combined / irrelevant / pro-forma /
  SPAC-redemption), and a before/after SUE-computability simulation
  restricted to the 3 verified small-cap CIKs from the prior probe.
- **`tests/test_h11_eps_tag_analysis.py`** (added, committed at `1b0dceb`):
  16 unit tests for the script's pure functions (`classify_tag`,
  `build_tag_classification`, `simulate_expanded_tag_priority`).
- **Script run locally** by the user against real SEC bulk data (3 CIKs,
  2020Q1-2022Q3), output pasted back, and `docs/H11_EPS_TAG_ANALYSIS.md`
  (added this milestone) written from that real output -- not from
  assumptions or synthetic data.

## Why it changed

Per the project's governing principle: whether to widen a measurement
definition is a research decision requiring a written amendment, never a
silent code change. Before drafting or even considering
`amendments/H11_AMENDMENT_002.md`, the actual evidence needed to be on the
table -- real tag frequencies, real namespace data, and a real (not
estimated) impact simulation.

## Key findings (see `docs/H11_EPS_TAG_ANALYSIS.md` for full detail)

- The 40.8% name-based "custom-tag rate" and the 0.8% namespace-based rate
  disagree by ~50x. The gap is almost entirely one tag: `EarningsPerShareBasic`
  (191,941 of 482,711 EPS-like facts industry-wide, 39.8%), a standard
  `us-gaap` tag, not a company-invented extension.
- Of the top-50 tags (99.4% of the full population): ~40% diluted-only,
  ~40% basic-only, ~21% already-accepted combined, under 0.3% irrelevant-to-EPS
  or a different construct (pro-forma, SPAC-redemption).
- For the 3 verified small-cap CIKs specifically: adding `EarningsPerShareBasic`
  as a fallback tier changed **zero** SUE-computability outcomes -- every
  quarter for all 3 firms already had `EarningsPerShareDiluted` or
  `EarningsPerShareBasicAndDiluted` reported. This is not evidence the
  question is unimportant industry-wide (Basic-only facts are ~40% of the
  full population), only that it made no difference for the specific 3
  firms tested so far.
- Basic and Diluted EPS are different constructs (dilutive securities are
  excluded from the Basic share count). Adding Basic EPS as a fallback would
  risk mixing constructs within a single firm's SUE series depending on
  which tag a given quarter happened to file under -- a construct change to
  the surprise measure, not simply "more of the same data."

## New assumptions introduced

None. The script reuses `extract_eps_records()`'s existing override
parameter; no new extraction logic or assumption was added.

## New invariants introduced

None. No production code changed.

## Validation performed

- **231/231 tests pass** (`python -m pytest tests/`) after the script and
  its 16 tests were added.
- Two fragile test fixtures (linear EPS value series producing zero/near-zero
  variance) were caught and replaced with explicit non-linear hardcoded
  values during test development, before this milestone's commit.
- Script output verified against real SEC bulk data, run by the user
  locally (sandbox has no network access to `data.sec.gov`); the analysis
  document was written only after real JSON output was pasted back, not in
  advance of it.

## Remaining risks

Carried forward from the prior milestone, plus this milestone's own:

1. 8-K/A amendment fallback (original omits Item 2.02, amendment adds it)
   still not implemented.
2. CIK -> ticker resolution in the probe is still current-ticker-only, not
   point-in-time.
3. Whether `EPS_TAG_PRIORITY` should be widened to include
   `EarningsPerShareBasic` remains **unresolved** -- this milestone provides
   evidence, not a decision. No amendment has been drafted.
4. The Basic-EPS impact simulation covers only 3 CIKs; whether Basic-only
   quarters are concentrated in particular sectors, sizes, or filing
   patterns within H11's actual $50M-$2B universe is unknown -- the tag
   distribution is industry-wide, not universe-filtered.
5. The `_STANDARD_TAXONOMY_PREFIXES` completeness (namespace-based custom-
   tag rate) is unverified against SEC's full taxonomy list.
6. The duplicate-submissions-endpoint-per-CIK pattern is still visible in
   telemetry but not fixed.

## Specific areas where external review should focus

1. **Whether the construct-mixing concern (Basic vs. Diluted EPS as
   economically different measures) is itself correctly reasoned** -- this
   is the central argument against treating "add Basic EPS" as a pure
   data-completeness improvement, and it's worth checking independently
   rather than taking the document's framing at face value.
2. **Whether 3 CIKs is a large enough sample to conclude "zero impact for
   now" is meaningful**, or whether this simulation needs to run against a
   wider CIK set before any amendment decision is made.
3. **The `classify_tag()` heuristic itself** (documented in the script as
   "a judgment call, not a definitive taxonomy") -- worth a second look at
   whether any of the ~50 top tags are mis-bucketed, particularly the
   SPAC-redemption-pattern grouping given the project's explicit rule
   against adding SPAC exclusions without real evidence.
