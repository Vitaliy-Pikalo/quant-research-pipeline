# REVIEW.md -- Milestone: H11 market-cap/ADV probe (stage 2 bottleneck), in progress

Per the standing workflow: this is the handoff document for external
(GitHub-based) review of this milestone. Supersedes the prior milestone's
`REVIEW.md` (preserved in git history at `901dae6`).

**Scope note, stated up front:** this milestone is engineering only --
building the market-cap/ADV data pipeline stage 2 needs and doesn't yet
exist (per `H11_data_availability_review.md` section 5's finding that
CIK-keyed joins, not a rebuilt ticker-history database, is the correct
mitigation for the CIK<->ticker risk). It does not touch
`H11_PREREGISTRATION.md`, `EPS_TAG_PRIORITY`, or any prior amendment. No
real universe has been built yet -- this milestone is still mid-validation
as of this REVIEW.md.

## What changed

- **`data_connectors/sec_financial_statement_datasets.py`**:
  `extract_shares_outstanding()` added -- new function, entirely separate
  from EPS extraction, for market-cap construction. Sums all reported
  share-class rows per (cik, ddate, adsh) per
  `H11_data_availability_review.md` section 5's dual-class mitigation,
  rather than deduplicating down to one the way EPS tag competition works.
- **`data_connectors/market_data_yfinance.py`** (new file): yfinance
  price/volume fetch (untested here, network) plus two pure, tested
  functions -- `price_as_of()` (latest close on or before a date, `None`
  rather than a silently-wrong future price) and
  `trailing_median_dollar_adv()` (20-trading-day trailing MEDIAN dollar
  volume, strictly before the reference date, matching
  `H11_IMPLEMENTATION_SPEC.md` section 3's exact definition -- median, not
  mean, deliberately robust to one outlier trading day).
- **`backtests/h11_market_cap_probe.py`** (new file): real small-scale
  probe, same 3 verified CIKs and 11-quarter window as the prior two
  probes, joining shares outstanding x price into real market cap and ADV,
  running the existing `event_study.universe.qualify_row()` against
  H11's real cap band. Ticker is only introduced for the price join and
  written to a separate `ticker_resolution_for_review.csv` for manual
  eyeball review (real SEC company name, exchange, former names), never
  auto-trusted -- per this project's standing CIK-first, ticker-only-where-
  unavoidable design for this exact risk category.
- **Corrected mid-milestone**: `SHARES_OUTSTANDING_TAG_PRIORITY` originally
  defaulted to `EntityCommonStockSharesOutstanding` (a dei cover-page tag),
  on the assumption that a required cover-page element would have
  near-universal coverage. The first real run against live SEC data
  produced 0 usable candidate rows. Investigated per the standing rule
  (real attrition gets investigated, not filtered around) rather than
  tuned blindly: a real-data diagnostic showed that tag has only 3 total
  rows in a full quarter's bulk file, because SEC's Financial Statement
  Data Sets are built from the financial statements themselves, not the
  document cover page. `CommonStockSharesOutstanding` (a real us-gaap
  balance-sheet/equity-note tag, 27,424 rows in the same quarter, same
  confirmed instant-type/`qtrs==0` behavior) is now the primary tag; the
  original tag is kept as a documented low-priority fallback, not removed.

## Why it changed

`H11_IMPLEMENTATION_SPEC.md` stage 2 needs `market_cap` and `adv_20d` per
firm-quarter, and neither existed anywhere in this codebase before this
milestone. This is the concrete implementation of the "real market data at
scale" gap identified when scoping the full event-dataset build -- the
biggest remaining bottleneck, per the corresponding scoping discussion, is
not the CIK<->ticker mapping (already mitigated by design) but the
market-cap data itself.

## New assumptions introduced

- Market cap and ADV in this probe are computed as of `period_end` (the
  quarter-end date), NOT the true `known_at` the spec requires (the 8-K/
  10-Q event timestamp). Flagged explicitly in the script's own docstring
  as a deliberate, temporary simplification -- must be corrected (joining
  to the real `known_at` from `h11_data_probe.py`'s pipeline) before this
  feeds any real universe build, not silently treated as equivalent.
- `CommonStockSharesOutstanding` is now assumed to be the reliable primary
  shares-outstanding source. This assumption is corrected-once already
  (see above); it has NOT yet been validated against the real run for the
  3 target CIKs specifically -- that's the next step, not yet complete as
  of this REVIEW.md.

## New invariants introduced

None in production logic. `qualify_row()` and `UniverseConfig` are reused
unchanged from existing, already-tested code.

## Validation performed

- **247/247 tests pass** (`python -m pytest tests/`), up from 231 --
  7 new tests for `extract_shares_outstanding()` (single-class, dual-class
  summation, duration-fact exclusion, cross-filing non-summation, fallback
  tag priority, missing columns, empty input) and 8 for the price connector's
  pure functions (exact-date lookup, weekend/holiday rollback, pre-IPO
  `None`, empty series, median-window correctness, median's outlier
  robustness vs. a mean, insufficient-history `None`).
- The tag-priority bug above was caught by a REAL run producing 0 rows,
  not by a unit test (the unit tests were fixture-based and could not have
  caught a wrong assumption about which real-world tag is populated) --
  investigated via a throwaway diagnostic script against real live SEC
  data rather than guessed at a second time.
- **Not yet validated**: a real run against the 3 target CIKs with the
  corrected tag has not been completed as of this REVIEW.md. That is the
  explicit next step, not assumed to work from the fixture tests alone.

## Remaining risks

Carried forward, plus this milestone's own:

1. 8-K/A amendment fallback still not implemented.
2. `market_cap`/`adv_20d` computed at `period_end`, not `known_at` -- must
   be corrected before any real universe build (see above).
3. Whether `EPS_TAG_PRIORITY` should be widened remains unresolved,
   deferred pending real attrition evidence from a future full build --
   no amendment drafted.
4. `CommonStockSharesOutstanding` coverage for the 3 actual target CIKs is
   still unconfirmed by a real run as of this REVIEW.md.
5. The BRKL-style low-trading-day-count flag (`< 100` trading days) is a
   smell test, not a guarantee -- a recycled ticker with a long enough
   fake history would not be caught by this check alone; the
   `ticker_resolution_for_review.csv` manual review step is the real
   safeguard.
6. The `_STANDARD_TAXONOMY_PREFIXES` completeness is unverified against
   SEC's full taxonomy list.
7. The duplicate-submissions-endpoint-per-CIK telemetry pattern is still
   visible but not fixed.

## Specific areas where external review should focus

1. **Whether `CommonStockSharesOutstanding` is really the right primary
   tag**, or whether it has its own gaps this quarter's diagnostic
   (a single quarter, all filers, not the 3 target CIKs specifically)
   didn't surface -- the pending real run against the actual target CIKs
   is the next real test of this.
2. **The `period_end`-vs-`known_at` simplification** -- confirm this
   milestone's own docstring flag is loud enough that a future session
   doesn't accidentally treat this probe's market_cap numbers as
   spec-compliant before the correction is made.
3. **The manual ticker-review step's actual rigor** -- `qualify_row()`
   trusts `listing_exchange` and `market_cap` the moment they're computed;
   confirm the review step happens BEFORE those numbers get used
   downstream, not after, given the human-review gate is currently a
   process convention, not a code-enforced gate.
