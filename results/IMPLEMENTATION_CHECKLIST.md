# H11 implementation checklist

Sequential. Each phase has a gate — don't start the next phase until the
current one's diagnostics are recorded and reviewed. Every box checked
should move toward a publishable result regardless of whether H11 ends up
supported or not; a clean, well-diagnosed null is as much a completed box
as a clean positive.

## Ground rules (apply to every phase below, not just one)

- [ ] **Smallest vertical slice first.** `h11_data_probe.py` runs end-to-end
      on ~100 events before anything scales to the full 2015–2025 panel.
- [ ] **Every transformation emits a diagnostic**, written to a file, not
      just printed — % fallback tags, % missing EPS, % unmatched CIKs, %
      amended filings, event attrition per filter, at minimum.
- [ ] **Every stage's output is a preserved, inspectable file** — no stage
      may only exist as an in-memory object inside a larger script.
- [ ] **Unexpected attrition is a bug until proven otherwise.** If usable
      events fall materially below the data-availability review's
      30,000–60,000 planning range, stop and investigate before continuing,
      the same way H10's silent 61-bank-year deletion was treated as a bug
      once found, not a footnote.
- [ ] **Any forced deviation from `H11_PREREGISTRATION.md` stops work** and
      gets written up as a separate amendment document — the original
      pre-registration is never edited post-freeze.

---

## Phase 0 — vertical slice (gate before everything else)

- [ ] Write `backtests/h11_data_probe.py`.
- [ ] Pull 2–3 sample quarters of SEC Financial Statement Data Sets.
- [ ] Resolve a small known set of small-cap CIKs end-to-end: EPS tag →
      SUE → 8-K Item 2.02 timestamp → price-panel ticker.
- [ ] Confirm on ~100 events: point-in-time timestamps look correct
      (`known_at` strictly after `period_end`), ticker resolution succeeds
      without a silent mismatch, EPS tag extraction hits the standard tag
      more often than not.
- [ ] Record diagnostics from this slice before writing one more line of
      the full pipeline.
- **Gate:** if the 100-event slice shows a fallback rate, unmatched-CIK
  rate, or timestamp anomaly rate high enough to threaten the data-
  availability review's assumptions, stop and revisit before scaling — this
  is the cheapest possible point to catch a structural problem.

## Phase 1 — data acquisition

- [ ] Bulk-pull SEC Financial Statement Data Sets for all quarters,
      2015–2025 (primary source, per the data-availability review).
- [ ] Pull 8-K index/timestamps for Item 2.02 filings over the same window.
- [ ] Pull SEC's official `company_tickers.json` and `submissions` API
      output for CIK metadata (names, SIC codes, former names).
- [ ] Preserve each raw pull as its own file, dated, before any joining.
- [ ] Diagnostic: row counts per quarter, compared against SEC's own
      published filing-volume figures where available, as a sanity floor.

## Phase 2 — point-in-time validation

- [ ] For every event, verify `known_at` (8-K Item 2.02 accession
      timestamp, or 10-Q/10-K fallback) is strictly later than the fiscal
      period it describes.
- [ ] Verify EPS values used are as-filed, not restated — spot-check
      against a sample of companies with a known restatement history
      (pre-registration §13.1).
- [ ] Diagnostic: % events using the 10-Q/10-K fallback instead of a direct
      8-K Item 2.02 (pre-registration §13.4 / §4.2).
- [ ] Diagnostic: % events flagged for 8-K/A amendment handling, and
      confirmation the *original* filing's timestamp was used, not the
      amendment's.
- **Carried-forward risk:** 8-K edge-case coverage loss. This phase is
  where it either shows up in the numbers or it doesn't — report honestly
  either way.

## Phase 3 — identifier resolution

- [ ] Resolve CIK → point-in-time ticker → existing price-panel symbol.
- [ ] Cross-check every match against company name and SIC-implied
      industry, not ticker alone.
- [ ] Apply the minimum-observations gate (same category of check that
      caught the recycled BRKL ticker in H10).
- [ ] Diagnostic: % unmatched CIKs, % matches requiring the fallback
      cross-check, full mapping published as its own reviewable file (same
      standard as H10b's locality-mapping publication).
- **Carried-forward risk:** point-in-time CIK↔ticker resolution — the one
  mapping step in this design in the same risk category as this project's
  four prior mapping bugs. Treat this phase's diagnostics with the most
  scrutiny of any phase.

## Phase 4 — feature construction

- [ ] Compute SUE (seasonal random walk, as-filed EPS, 8-quarter volatility
      window) per pre-registration §5.
- [ ] Compute the secondary 3-day announcement-CAR surprise measure.
- [ ] Build the size/sector matched-control portfolio per §7.
- [ ] Diagnostic: % events resolving EPS via the standard tag vs. the
      fallback tag-priority list vs. unresolvable (excluded, counted).
- [ ] Diagnostic: event attrition table — count remaining after each filter
      (market cap, listing, XBRL history, M&A exclusion), so the final
      usable-event count is fully traceable to the raw pull.
- **Carried-forward risk:** custom XBRL extension tags. This is the phase
  where the fallback-tag diagnostic either confirms or contradicts the
  data-availability review's expectation that this concentrates in smaller
  filers.

## Phase 5 — cost model

- [ ] Compute 20-day median dollar ADV per event, per pre-registration §9.
- [ ] Apply the liquidity-scaled cost schedule (bucketed, not flat).
- [ ] Diagnostic: distribution of events across ADV buckets — if the
      universe skews heavily into one bucket, that's reported before
      interpreting net returns, not after.
- **Carried-forward risk:** transaction costs deciding the outcome rather
  than raw alpha. This phase's output is what §12 of the pre-registration
  actually adjudicates — treat the by-bucket net-return table as the
  headline result, not the pooled raw-return number.

## Phase 6 — cross-validation

- [ ] Set up `cv.py` walk-forward splits for the strategy backtest (test
      #4 in the pre-registration).
- [ ] Purge/embargo windows around each fold boundary, consistent with
      every prior hypothesis in this project.
- [ ] Diagnostic: confirm no train/test overlap via the existing purge/
      embargo test suite before trusting any fold's output.

## Phase 7 — statistical testing

- [ ] Run test #1 (primary pooled rank-IC) — block bootstrap by
      announcement week for the p-value.
- [ ] Run test #2 (60-day holding secondary).
- [ ] Run test #3 (CAR-based surprise measure secondary).
- [ ] Run test #4 (decile strategy, net of liquidity-scaled costs, by ADV
      bucket, deflated Sharpe).
- [ ] Apply BH-FDR across this test batch.
- [ ] Evaluate deflated Sharpe at the correct cumulative trial count (82,
      since H11 runs before H12 — pre-registration §12).

## Phase 8 — robustness checks

- [ ] Reversal/momentum breakdown, reported regardless of outcome.
- [ ] Split-half replication (first half vs. second half of 2015–2025).
- [ ] Fallback-source-only vs. direct-8-K-only sub-samples compared, to
      confirm the coarser-precision fallback events aren't silently
      driving the result.

## Phase 9 — result reporting

- [ ] Apply the pre-registration §12 decision rule exactly as written — no
      new criteria introduced after seeing results.
- [ ] Report net-of-cost result by ADV bucket as the headline, not the
      pooled number, per §12's tradeability framing.
- [ ] Publish every diagnostic table from phases 1–8 alongside the result,
      not just the ones that support the conclusion.
- [ ] Write the H11-vs-H10/H10b postmortem: which pre-registered
      assumptions mattered most, what that implies for H12 and beyond.
- [ ] If any deviation from the pre-registration occurred during
      implementation, confirm it's documented in a separate amendment file,
      not folded into the original.
