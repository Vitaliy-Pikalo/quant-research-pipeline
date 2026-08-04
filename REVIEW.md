# REVIEW.md -- Milestone: H11 market-cap/ADV probe (stage 2 bottleneck), validated against real data

Per the standing workflow: this is the handoff document for external
(GitHub-based) review of this milestone. Supersedes the prior milestone's
`REVIEW.md` (preserved in git history at `901dae6`).

**Scope note, stated up front:** this milestone is engineering only --
building the market-cap/ADV data pipeline stage 2 needs and didn't
previously exist (per `H11_data_availability_review.md` section 5's
finding that CIK-keyed joins, not a rebuilt ticker-history database, is the
correct mitigation for the CIK<->ticker risk). It does not touch
`H11_PREREGISTRATION.md`, `EPS_TAG_PRIORITY`, or any prior amendment.

## What changed

- **`data_connectors/sec_financial_statement_datasets.py`**:
  `extract_shares_outstanding()` added, plus `flag_implausible_shares_jumps()`.
  Sums all reported share-class rows per (cik, ddate, adsh) per
  `H11_data_availability_review.md` section 5's dual-class mitigation, then
  collapses to exactly one row per real (cik, period_end) -- preferring
  the filing whose OWN reporting period matches that date over a later
  filing merely echoing it as a prior-year comparative, falling back to
  earliest-filed if no filing's own period matches.
- **`data_connectors/market_data_yfinance.py`** (new file): yfinance
  price/volume fetch (untested here, network) plus two pure, tested
  functions -- `price_as_of()` and `trailing_median_dollar_adv()`
  (20-trading-day trailing MEDIAN, not mean, dollar volume, strictly
  before the reference date, matching `H11_IMPLEMENTATION_SPEC.md`
  section 3 exactly).
- **`backtests/h11_market_cap_probe.py`** (new file): real probe, same 3
  verified CIKs and 11-quarter window as the prior two probes, joining
  shares outstanding x price into real market cap and ADV, running
  `event_study.universe.qualify_row()` against H11's real cap band, and
  surfacing both the implausible-jump flag and a manual ticker-review CSV
  (SEC company name, exchange, former names) -- never auto-trusting the
  ticker join, per this project's CIK-first design for this risk category.
- **Two real bugs found and fixed via live SEC data, not guessed at in
  advance:**
  1. `SHARES_OUTSTANDING_TAG_PRIORITY` originally defaulted to
     `EntityCommonStockSharesOutstanding` (a dei cover-page tag), on the
     assumption a required cover-page element would have near-universal
     coverage. First real run: 0 usable rows. A real-data diagnostic
     showed that tag has only 3 total rows in a full quarter's bulk file
     (SEC's Financial Statement Data Sets are built from the financial
     statements, not the cover page). Fixed: `CommonStockSharesOutstanding`
     (a real us-gaap balance-sheet tag, 27,424 rows same quarter) is now
     primary; the original tag is a documented low-priority fallback.
  2. After that fix, a real run against the 3 target CIKs produced 114
     candidate rows where ~29 real firm-quarters were expected -- the same
     true balance was being echoed once per later filing that reported it
     as a prior-year comparative (e.g. POWL's 2019-12-31 value appeared
     6 times). Fixed via the collapse-to-one-row-per-real-period logic
     above. Separately, the same real run surfaced a genuine filer XBRL
     scaling error: Lakeland Industries' 2020-01-31 and 2020-07-31 shares
     outstanding were tagged 1000x too high in one comparative echo
     (7,972,423,000 vs. the correct 7,972,423) -- caught incidentally by
     the cap-band gate (`market_cap_above_max`) but not explained until
     investigated; `flag_implausible_shares_jumps()` now flags this
     deterministically for human review rather than relying on the cap
     band to accidentally absorb it.

## Why it changed

`H11_IMPLEMENTATION_SPEC.md` stage 2 needs `market_cap` and `adv_20d` per
firm-quarter, and neither existed anywhere in this codebase before this
milestone. This is the concrete implementation of the "real market data at
scale" gap identified when scoping the full event-dataset build.

## New assumptions introduced

- Market cap and ADV in this probe are computed as of `period_end` (the
  quarter-end date), NOT the true `known_at` the spec requires. Flagged
  explicitly in the script's own docstring as a deliberate, temporary
  simplification -- must be corrected before this feeds any real universe
  build.
- `CommonStockSharesOutstanding`, collapsed to one row per real period, is
  now the shares-outstanding source of record. Validated against the 3
  target CIKs specifically (see below), not just a same-quarter,
  all-filers diagnostic.
- `flag_implausible_shares_jumps()`'s >5x/<0.2x threshold is a first-pass,
  documented-as-provisional choice, not independently tuned against a
  larger sample yet.

## New invariants introduced

None in production logic. `qualify_row()` and `UniverseConfig` are reused
unchanged from existing, already-tested code.

## Validation performed

- **253/253 tests pass** (`python -m pytest tests/`), up from 231 at the
  start of this milestone -- covering single/dual-class summation,
  duration-fact exclusion, cross-filing non-summation, the comparative-echo
  collapse (including the fallback-to-earliest-filed edge case), the
  fallback tag tier, the price connector's date/median-window logic
  (including median's robustness to a single outlier day, matching the
  real Lakeland case in kind), and the implausible-jump flag (including
  its documented symmetric-flagging limitation).
- **Real run completed** against the 3 verified CIKs, 11 quarters
  (2020Q1-2022Q3): 173,191 shares-outstanding rows found across the full
  bulk population; 114 candidate rows for the 3 target CIKs pre-fix
  (duplicated by comparative echoes), 88 with a usable market cap, 86
  qualifying H11's $50M-$2B cap band. Both real bugs above were caught by
  this real run, not by the fixture-based unit tests, which by design
  cannot catch a wrong assumption about which real-world tag or join
  behavior actually holds.
- **Re-run completed and confirmed** against the 3 target CIKs with both
  fixes active together: candidate rows dropped from 114 (pre-collapse,
  duplicated) to 44, each a distinct (cik, period_end) -- zero remaining
  duplicates. The Lakeland anomaly is now fully explained, not just
  caught: the collapse logic shows the bad 1000x value
  (`is_own_reporting_period=True` for 2020-07-31) originates in that
  filing's OWN primary tag, not a comparative echo -- a genuine filer
  XBRL error, confirmed by two independent signals (the implausible-jump
  flag AND the cap-band gate's `market_cap_above_max`). The earlier
  billions-value duplicate at 2020-01-31 was correctly discarded by the
  same collapse logic, since that one really was just a bad echo, not the
  filing's own data -- the two cases are mechanically different and the
  fix distinguishes them correctly on real data, not by luck.

## Remaining risks

Carried forward, plus this milestone's own:

1. 8-K/A amendment fallback still not implemented.
2. `market_cap`/`adv_20d` computed at `period_end`, not `known_at` -- must
   be corrected before any real universe build.
3. Whether `EPS_TAG_PRIORITY` should be widened remains unresolved,
   deferred pending real attrition evidence from a future full build.
4. `flag_implausible_shares_jumps()`'s ratio threshold is provisional and
   symmetric (flags both sides of a real jump, since 3 points alone can't
   identify which side is wrong) -- a human still has to look, this does
   not auto-correct anything.
5. The BRKL-style low-trading-day-count flag (`< 100` trading days) is a
   smell test, not a guarantee; `ticker_resolution_for_review.csv`'s
   manual review is the real safeguard, and is currently a process
   convention, not a code-enforced gate.
6. The `_STANDARD_TAXONOMY_PREFIXES` completeness is unverified against
   SEC's full taxonomy list.
7. The duplicate-submissions-endpoint-per-CIK telemetry pattern is still
   visible but not fixed.

## Specific areas where external review should focus

1. **Whether the comparative-echo collapse's tie-break (own-period filing,
   else earliest-filed) is the right choice**, particularly for the rare
   case where a company genuinely restates a prior figure (not just
   echoes it) -- this logic currently cannot distinguish "echo" from
   "genuine restatement," and always prefers the earlier value either way.
2. **Whether the 1000x Lakeland error is really a filer mistake and not a
   real corporate action** (e.g. a genuine share issuance) that happens to
   look like a scaling error -- worth an independent eyeball at the actual
   filing before fully dismissing it as a tagging bug.
3. **The manual ticker-review step's actual rigor** -- confirm the review
   happens BEFORE `market_cap`/`qualifies_cap_band` numbers get used
   downstream, not after, given this gate is a process convention, not a
   code-enforced one.
