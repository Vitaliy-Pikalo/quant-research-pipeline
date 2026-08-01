# Research timeline

One-page roadmap. This exists so the repository reads as a disciplined
research program with pre-committed decision rules, not a collection of
independent backtests run until one looks good.

## Sequence so far

| # | hypothesis | trials spent | result |
|---|---|---|---|
| H9 | FX carry (UIP violation) | 46 | not supported — pooled IC −0.0125, p=0.073 |
| H8 | 13F institutional copycat | 6 | not supported once market-adjusted |
| H10 | Beige Book district sentiment | 23 | not supported — IC 0.015, 0/12 districts survive FDR |
| H10b | Beige Book, locality-weighted | 3 | not supported — and falsified H10's own stated explanation |
| **running total** | | **78** | **0 of 4 supported** |

## What's queued

| # | hypothesis | status | trials it will spend | cumulative after |
|---|---|---|---|---|
| **H11** | Point-in-time PEAD, modern sample, liquidity-scaled costs | pre-registered, frozen, pending commit | 4 | **82** |
| **H12** | Small-cap insider cluster buying | pre-registered, frozen, queued behind H11 | 4 | **86** |

H11 runs first on methodological grounds, not because it's expected to work
better — larger sample, no new hand-built entity mapping, near-drop-in
pipeline fit, and a materially cheaper way to answer a prior question: does
*any* free-data equity anomaly survive this project's evaluation framework
at all, before committing to H12's heavier Form-4-ingestion build. Full
reasoning: `H11_prioritization_review.md`, `H11_rationale.md`.

## Decision gate after H11

Evaluated strictly against `H11_PREREGISTRATION.md` §12, no new criteria
introduced after seeing results:

- **Supported** (positive IC, clears block bootstrap, positive net of the
  liquidity-scaled cost schedule in ≥1 ADV bucket, DSR > 0.95 at 82 trials)
  → proceed to H12 with added confidence that this project's methodology can
  detect a real signal when one exists, not just produce clean nulls.
- **Real but untradeable at every liquidity level** → still proceed to H12
  (different mechanism, doesn't inherit this problem by default per its own
  §16), but flag that free-data-tier transaction costs are a binding
  constraint across hypotheses, not specific to PEAD — raises the bar for
  how seriously H12's own 50bps assumption needs auditing before trusting
  a positive result there.
- **Not supported** → proceed to H12 anyway (already pre-registered,
  independent mechanism, not contingent on H11), but this becomes the fifth
  null out of five, which is itself information — see pivot conditions below.

## Decision gate after H12

Evaluated strictly against `H12_PREREGISTRATION.md` §10:

- **Supported** → first positive result in the project. Next hypothesis
  (H13+) gets chosen by extending whichever mechanism worked (informational/
  capacity-constrained vs. behavioral/cost-constrained), not by defaulting
  back to the dossier's original priority order.
- **Not supported** → sixth null. Triggers the pivot review below rather
  than an automatic H13.

## Conditions that would trigger a pivot away from this research direction

Not "any null triggers a pivot" — a single null is a normal outcome and has
been the modal result of this project so far. The conditions that would
specifically justify stepping back from *free-data equity anomalies as a
category*, rather than just picking hypothesis #13:

1. **Both H11 and H12 come back null or untradeable.** Six hypotheses, zero
   survive, spanning macro (FX, Beige Book), institutional-flow (13F), and
   two structurally different equity anomalies (behavioral/PEAD,
   informational/insider). That is a real signal about the ceiling of what
   $0-budget data can support, not noise — worth a dedicated review before
   spending a seventh trial, the same way the Beige Book family got a
   dedicated review after its second null (H10b) rather than a third
   automatic attempt.
2. **A result is supported only through the cost-model's most favorable
   assumption**, i.e. it clears the decision rule but the net-of-cost margin
   is thin enough that a plausible, still-defensible alternative cost
   assumption would flip it. That's a fragile "supported," not a real one,
   and should be treated closer to a null for direction-setting purposes.
3. **Deflated Sharpe keeps compressing toward the Harvey-Liu-Zhu t>3
   threshold implemented in `stats.py`** as the cumulative trial count rises
   (78 → 86 → ...) — at some point the multiple-testing penalty alone makes
   it structurally hard for *any* new free-data hypothesis to clear the bar,
   independent of whether the underlying effect is real. If that point is
   being approached, the honest move is a genuinely independent research
   program with its own fresh trial count (as flagged as Option C for Beige
   Book), not squeezing one more test out of the current one.

None of these are close to triggering yet — this section exists so the
threshold is written down before it matters, not decided in the moment a
null result is sitting on the screen.

## Cumulative trial count ledger

```
78  (H9 46 + H8 6 + H10 23 + H10b 3)  — baseline, carried from prior work
82  after H11 (PEAD)                  — +4
86  after H12 (insider clusters)      — +4
```

Every subsequent hypothesis's deflated Sharpe threshold is evaluated against
whatever this running total is at the time it's tested — never reset per
hypothesis, per this project's standing rule.
