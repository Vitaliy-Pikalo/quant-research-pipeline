# REVIEW.md -- Milestone: real `known_at` wired into market cap / ADV (amendment 002), validated against real data

Per the standing workflow: this is the handoff document for external
(GitHub-based) review of this milestone. Supersedes the prior milestone's
`REVIEW.md` (preserved in git history at `c38e96e`).

**Scope note, stated up front:** this milestone is mixed, and the two halves
are deliberately kept in separate commits. The engineering half (form
filtering, filing selection, single-fetch submissions parsing, the known_at
panel) shipped on its own merits. The research half — *which observable daily
bar operationalises "price at `known_at`"* — went through
`amendments/H11_AMENDMENT_002.md`, approved 2026-08-04, **before** the first
`known_at`-based run produced any output. `H11_PREREGISTRATION.md` is
untouched. `EPS_TAG_PRIORITY` is untouched.

## What changed

- **`hypotheses/h11_pead/known_at_resolver.py`** (new): resolves
  `(cik, period_end) -> (known_at, event_source)` for **every** firm-quarter.
  The prior inline implementation in `h11_data_probe.py` resolved one quarter
  per CIK (`firm_eps.index.max()`), which a universe build cannot use. Pure,
  no network, fully fixture-tested.
- **`data_connectors/sec_8k_item202.py`**: added
  `parse_submission_filings_for_periodic()` and `fetch_raw_submission()`. The
  probe now makes **one** submissions request per CIK and parses it three ways
  (identifiers, Item 2.02 8-Ks, periodic acceptance timestamps) instead of
  hitting the identical URL three times — closing the duplication this file's
  own docstring had flagged from telemetry.
- **`data_connectors/market_data_yfinance.py`**: added
  `known_at_to_price_panel_bound()`, `last_printed_close()` and
  `entry_bar_close()`. `price_as_of()` is no longer used by the probe.
- **`backtests/h11_market_cap_probe.py`**: the `period_end` substitution its
  own docstring flagged as requiring correction is **gone**. `market_cap` and
  `adv_20d` are now evaluated at the real `known_at`.
- **`backtests/h11_data_probe.py`**: engineering fix only (see defect 1
  below), shipped in its own commit ahead of the amendment.

## Three real defects in the prior known_at path

All three were found by reading the prior inline implementation against the
SEC Financial Statement Data Sets schema, then confirmed against real data —
not by guessing.

1. **No form filter.** `sub_all[(cik == ...) & (period == ...)]` matched any
   form in `sub.txt`, which carries 8-K, 20-F, 40-F, S-1 and 424B* alongside
   periodic reports. A non-periodic form could have supplied the "10-Q"
   timestamp.
2. **Arbitrary row selection.** `.iloc[0]` on an unsorted frame. Where several
   filings cover one period, the `filed` date used was whatever pandas ordered
   first. Now: periodic originals only, **earliest filed wins** — the
   as-first-reported principle `extract_shares_outstanding()` already applies
   to its own tiebreak.
3. **Date-only `filed` read as UTC midnight.** `sub.txt`'s `filed` is a bare
   `YYYYMMDD`. Parsing it as midnight UTC and converting to Eastern places a
   filing at **20:00 ET on the previous calendar day**:

   ```
   >>> pd.to_datetime('20200501', format='%Y%m%d', utc=True).tz_convert('US/Eastern')
   Timestamp('2020-04-30 20:00:00-0400')
   ```

   Consequence: an 8-K Item 2.02 accepted the same morning as the 10-Q gives
   `gap_days == -1`, fails `determine_known_at`'s `0 <= gap_days` guard, and
   the event silently downgrades to the 10-Q fallback — losing the primary
   source §4 prefers and mislabelling `event_source`, which §4.2 requires to
   be accurate.

   **Not unilaterally "fixed."** Every replacement convention changes real
   `known_at` values and therefore entry dates. What shipped instead: the
   resolver prefers the periodic filing's **real `acceptanceDateTime`** from
   the submissions API, which removes the ambiguity rather than resolving it
   (engineering, no amendment needed); and where no acceptance timestamp
   exists, the date-only convention is an explicit parameter **defaulting to
   the existing defective behaviour**, so introducing the resolver is provably
   number-neutral. `amendments/H11_AMENDMENT_003_DRAFT.md` holds the open
   decision, deliberately as a draft — see Remaining risks.

## Two defects in this milestone's own first real run

Both were introduced by this milestone's code and caught by its first real
run, not by unit tests. Recorded here rather than quietly corrected.

1. **The `event_source` breakdown was measuring nothing.** The first run
   reported `10q_fallback: 67447` vs `8k_item202: 19`, which reads as "the
   primary source almost never fires." It was an artefact: `sub.txt` is a
   whole-population bulk file, but 8-K submissions are fetched per CIK, so
   ~67,434 rows resolved to fallback purely because their 8-Ks were never
   fetched. Fixed by scoping the panel to the requested CIKs (`ciks=`
   parameter, 5 regression tests). Scoped, the real ratio is **19 of 32
   (59%) primary-source**.
2. **The amendment 002 §6 diagnostic compared the wrong thing.** It compared
   the two *prices*, reporting "30 of 32 disagree." `last_printed_close()` and
   `entry_bar_close()` select **adjacent bars by construction** and therefore
   always differ — the metric was structurally incapable of being informative.
   §6 committed to measuring how many firm-quarters **qualify differently**.
   Corrected to run `qualify_row()` under both market caps and compare.

## Why it changed

`H11_IMPLEMENTATION_SPEC.md` §3 defines `market_cap` and `adv_20d` at
`known_at`. The prior probe substituted `period_end` and said so. That
substitution was the last thing standing between the validated 3-CIK vertical
slice and a full universe build that produces spec-compliant numbers on its
first run rather than needing a correction pass at full scale.

## New assumptions introduced

- **`market_cap` = shares × the last daily bar that had actually printed at
  `known_at`** (same-day close if `known_at` ≥ 16:00 ET, else the prior
  trading day's close). Approved as `H11_AMENDMENT_002.md`; candidate B
  (the bar the strategy transacts at) recorded there as
  considered-and-rejected, with reasoning.
- `adv_20d` unchanged in definition: strictly before `known_at`'s Eastern
  calendar date, which is §3's "as of the day before `known_at`" implemented
  literally.
- Amendments (`10-Q/A`, `10-K/A`) are excluded from `known_at` resolution —
  an amendment's date is not when the market first knew. See Remaining risks 2.
- The date-only `filed` convention remains the legacy (defective) one where no
  acceptance timestamp exists. Retained for number-neutrality, not because it
  is correct.

## New invariants introduced

None in production logic. `qualify_row()`, `UniverseConfig` and
`determine_known_at()` are reused unchanged.

## Validation performed

- **287/287 tests pass** (up from 253 at milestone start), covering: periodic
  form filtering, earliest-filed selection and its deterministic tie-break,
  amendment exclusion and its diagnostic counter, both date-only conventions
  and the rejection of an unknown one, the same-morning-8-K recovery case,
  latest-8-K-in-window selection, CIK scoping (5 regression tests written
  directly against defect 1 above), the price-bar rule either side of 16:00
  ET, and the tz-aware→tz-naive bridge **across a DST boundary** (US/Eastern
  is −05:00 in January and −04:00 in July; a fixed-offset bug passes every
  single-season test).
- **Real run completed**, 3 verified CIKs, 11 quarters (2020Q1–2022Q3):

  | measure | value |
  |---|---|
  | shares-outstanding rows (full bulk population) | 75,259 |
  | `known_at` resolved, scoped to the 3 CIKs | 32 |
  | — via 8-K Item 2.02 (primary source) | **19 (59%)** |
  | — via 10-Q/10-K fallback | 13 |
  | — with a real `acceptanceDateTime` | **32 (100%)** |
  | — via the date-only fallback | 0 |
  | candidate rows | 44 (unchanged from the prior milestone) |
  | with a usable market cap | 32 |
  | qualifying the $50M–$2B cap band | 32 |
  | no resolvable `known_at` (attrition, emitted not dropped) | 12 |
  | qualifying **differently** under the rejected entry-bar reading | **0** |

- **The 12 attrition rows were investigated, not accepted.** Eleven carry
  `is_own_reporting_period=False` — comparative echoes of 2017–2019 periods
  predating the pulled window, so no filing for them exists by construction.
  Correct attrition; under the prior `period_end` reading these rows were
  silently receiving a market cap for a quarter with no filing behind it.
- **The twelfth was investigated with a real-data diagnostic**
  (`backtests/_diag_missing_known_at.py`), not guessed at. CIK 798081
  (Lakeland), period 2020-07-31 — the same firm-quarter as the known 1000×
  XBRL tagging error — showed `is_own_reporting_period=True`, meaning a filing
  for that period *does* exist in the pulled data, yet produced no `known_at`.
  The diagnostic returned the reason directly: the only periodic filing for
  that period in range is `10-Q/A` (adsh `0001654954-20-010056`), and the
  original 10-Q is absent from the Financial Statement Data Sets entirely.
  Two further facts read off that output: the 1000× value therefore comes
  **from the amendment itself**, and Lakeland files Item 2.02 8-Ks routinely
  (8 of its other 10 quarters resolved to `8k_item202`), so a better
  `known_at` for this firm-quarter very likely exists and is simply not being
  reached. Written up as `amendments/H11_AMENDMENT_004_DRAFT.md`; **not
  patched.**

## What the zero disagreement count does and does not show

`qualification_differs_under_entry_bar_reading = 0` is the measurement
amendment 002 §6 committed to. **It is not evidence that the choice between
readings does not matter**, and must not be quoted as such:

- The two readings produce market caps differing by **3.95% on average and up
  to 17.6%** across these 32 rows. Prices do move between the bars.
- Qualification is unchanged only because every row sits far from a band edge:
  the range is **$57M–$222M** against a $50M–$2B band. The nearest row is 14%
  above the floor, and the largest observed price delta is larger than that
  margin.
- n = 32, from 3 hand-picked CIKs. At full scale, with a real cross-sectional
  distribution and tens of thousands of firm-quarters, some will sit on the
  boundary and the readings will diverge.

This sample got lucky; it is not structurally immune. The count is reported
because §6 requires it, and — per that same section — it is explicitly not
grounds for revisiting the decision in either direction.

## Remaining risks

Carried forward, plus this milestone's own:

1. **The date-only `filed` convention is still the legacy defective one**
   wherever no acceptance timestamp exists. This run showed 32/32 real
   timestamps — but only because 2020–2022 filings still sit in the
   submissions API's `filings.recent` block. A 2015–2020 build will look
   nothing like this. `H11_AMENDMENT_003_DRAFT.md` is held as a draft
   precisely because the number it needs does not exist yet.
2. **Amendment-only periods are dropped, not resolved.** 460 such periods in
   the full bulk population (~0.7% of 67,466 resolved pairs). Small, but
   plausibly concentrated among filers with messy XBRL — i.e. the small-cap
   tail this design targets. `H11_AMENDMENT_004_DRAFT.md`.
3. **CIK 723603 resolved to `10q_fallback` in all 11 quarters** while CIK
   80420 resolved to `8k_item202` in all 11. Either that filer does not file
   Item 2.02 8-Ks, or matching is failing for it. Not investigated. Flagged
   so it is not lost.
4. Everything remains proven at **3-CIK scale only**. The full filer universe
   is the next milestone and nothing here has been exercised against it.
5. `flag_implausible_shares_jumps()`'s ratio threshold is still provisional
   and symmetric.
6. The `< 100` trading-day flag and the manual `ticker_resolution_for_review.csv`
   step remain process conventions, not code-enforced gates.
7. Whether `EPS_TAG_PRIORITY` should be widened remains deferred pending real
   attrition evidence from a full build.
8. `_STANDARD_TAXONOMY_PREFIXES` completeness is still unverified against
   SEC's full taxonomy list.
9. Two interpreters are in use on the development machine (`python` → 3.14,
   `py` → 3.10, per `__pycache__` contents). Tests and probe runs have been
   executed under different ones. Should be pinned before the full build.

## Specific areas where external review should focus

1. **Amendment 002 §4 — the substantive decision.** Whether avoiding
   look-ahead in a *selection filter* is worth measuring `market_cap` on a
   different bar than the strategy transacts at. The rejected alternative and
   its case are recorded in §3–§4 of that document; a reviewer disagreeing
   should engage with it there rather than with the code.
2. **Whether "the last bar that had actually printed" is right at the
   boundary.** A filing accepted at exactly 16:00:00 ET is currently treated
   as having that day's close available. That is a judgement call about
   simultaneity, and it is not obvious.
3. **Whether dropping amendment-only periods is defensible at all**, given
   that a better `known_at` (the Item 2.02 8-K) is very likely available and
   simply is not being reached. See `H11_AMENDMENT_004_DRAFT.md` §3.
4. **The 59% primary-source rate.** Is 13 of 32 firm-quarters falling back to
   the 10-Q a reasonable rate for this population, or does it indicate the
   8-K matching window or item-detection is too strict? Risk 3 above may be
   the same question.
