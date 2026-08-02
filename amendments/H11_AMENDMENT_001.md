# H11 Amendment 001 — minimum XBRL history requirement for SUE construction

**Status: APPROVED (2026-08-01). No real SEC data has been pulled and
no return, IC, Sharpe, or p-value has been computed under this design.**

This amendment does not modify `results/H11_PREREGISTRATION.md`. Per this
project's standing rule, the frozen pre-registration is never silently
edited — any deviation discovered during implementation is recorded here,
separately, with a reason, and applied in code only after this document is
approved.

---

## 1. The conflict

`H11_PREREGISTRATION.md` §3 sets the universe's XBRL-history requirement:

> XBRL history: ≥5 consecutive quarters of diluted EPS on file, as-filed —
> "minimum needed to compute a seasonal SUE with an 8-quarter volatility
> window and at least one 4-quarter lag"

`H11_PREREGISTRATION.md` §5 defines the surprise measure that requirement is
meant to support:

> SUE(i, t) = [ EPS(i, t) − EPS(i, t−4) ] / std( EPS(i, t) − EPS(i, t−4) ),
> computed over the trailing 8 quarters of available history

These two statements are not arithmetically consistent. A single seasonal
difference d(t) = EPS(t) − EPS(t−4) needs 5 quarters of history (t−4 through
t). But §5's formula takes a **standard deviation** of seasonal differences,
not a single difference — and a standard deviation is undefined on one
observation. The minimum inputs needed at each level of strictness:

| interpretation | quarters required | seasonal diffs available | notes |
|---|---|---|---|
| §3's literal "5 consecutive quarters" | 5 | 1 | std of 1 point is undefined (n=1, ddof=1 → NaN) |
| absolute floor for a non-degenerate std | 6 | 2 | technically computable, extremely noisy |
| this implementation's chosen floor | 8 | 4 | `H11Config.min_seasonal_diffs = 4` |
| full 8-quarter volatility window as described in §5 | 12 | 8 | the complete window §5's prose describes |

This was discovered while implementing `compute_sue()`
(`hypotheses/h11_pead/event_generator.py`), not while re-reading the
pre-registration in the abstract — the code would not run against §3's
literal minimum without producing `NaN` or a divide-by-zero on the very
first firm-quarter tested. It is flagged here rather than resolved silently
in the module, per the standing rule that a methodology-affecting ambiguity
found mid-implementation gets an amendment, not a code comment alone.

---

## 2. Original specification

`H11_PREREGISTRATION.md` §3, XBRL history row: **≥5 consecutive quarters**.
This value is unchanged in the frozen document and remains the text of
record; this amendment proposes a superseding operational value for
implementation purposes only, exactly as `H12_PREREGISTRATION.md`'s own
amendment note (§ trial-count update) modified a downstream number without
editing H11's frozen text.

---

## 3. Proposed minimum history change

**Adopt 8 consecutive quarters as the minimum XBRL history requirement**,
i.e. `min_seasonal_diffs = 4` in `H11Config` (4 seasonal-difference
observations, on top of the 4-quarter lag itself: `sue_lag_quarters +
min_seasonal_diffs = 8`).

This is the middle option in the table above, not the two extremes:

- It rejects §3's literal 5-quarter floor, because that floor produces an
  undefined statistic (a std computed on one observation), not merely a
  noisy one — the pre-registration's own SUE formula cannot execute at that
  floor.
- It does not require the full 12-quarter window either. Requiring the
  complete 8-diff window before any firm qualifies would silently privilege
  firms with the longest, cleanest reporting histories, working against
  §3's own explicit design goal of not pre-filtering on liquidity or
  survivorship-adjacent characteristics. It would also cut disproportionately
  into the exact population — smaller, less-covered filers — that §1 of
  `H11_data_availability_review.md` already flags as carrying the most
  custom-tag and data-quality risk; further shrinking that segment's
  representation would work against the design's stated interest in testing
  whether the effect survives across the full liquidity spectrum, not just
  in the most established names.
- 4 seasonal-difference observations is the smallest window that still
  produces a std with a plausible degrees-of-freedom cushion (n=4, ddof=1 →
  3 residual degrees of freedom) rather than the near-zero-power case at
  n=2.

`np.std(window, ddof=1)` in `compute_sue()` already implements this
threshold; this amendment is what formally authorizes that implementation
choice rather than leaving it as an unapproved deviation.

---

## 4. Why this affects measurement feasibility, not the hypothesis itself

The hypothesis under test (§2 of the pre-registration) is about the
relationship between as-filed seasonal SUE and subsequent matched-control-
adjusted returns. Nothing about *how many quarters of trailing history are
required to compute SUE in the first place* touches that relationship,
the event definition (§4), the point-in-time rule (§6), the benchmark
construction (§7), or the cost model (§9). This is a **measurement
precondition** — how much history a firm needs before SUE can be computed
for it at all — not a change to what SUE means, how it is used, or what
outcome is predicted. The decision rule in §12 and the complete test list
in §11 are unaffected verbatim.

This is the same category of change as a data-availability constraint, not
a specification search: the pre-registration's own §14 ("declared in
advance — what will NOT be done") already commits to *not* searching over
the SUE window length or lag — that commitment is preserved here. This
amendment does not touch the window length (8 quarters, fixed) or the lag
(4 quarters, fixed); it only resolves how much trailing history must exist
before that fixed window can be evaluated at all, which the original text
left internally inconsistent.

---

## 5. Expected sample-size impact

`H11_data_availability_review.md` §4 estimated **30,000–60,000 usable
firm-quarter events** under the pre-registration's literal 5-quarter floor,
against a full 2015–2025 sample. That estimate is a desk estimate, not a
verified count, and was explicitly flagged there as needing local
confirmation.

Raising the floor from 5 to 8 quarters is expected to have a **small**
effect on that range, for a structural reason: the SEC's XBRL mandate
reached full coverage for the population this design targets (including
smaller reporting companies) by **June 2011** — nearly four years before
this sample's 2015-01-01 start. A firm that was already public and XBRL-
filing before 2015 has, by construction, well over 8 quarters of history
on file by the time it can enter this sample at all. The 5-versus-8-quarter
distinction only binds for:

1. **Firms that go public (or first begin XBRL filing) during the sample
   window itself** — for these firms, raising the floor delays their
   earliest qualifying event by 3 additional quarters (roughly 9 months)
   after IPO/first filing, rather than excluding them outright.
2. **Firms with a genuine gap in their filing history** (e.g. a late or
   skipped quarter) large enough that 8 consecutive quarters isn't
   available even though 5 would have been — expected to be a small
   fraction of firm-quarters, and already partially mitigated by
   `H11_data_availability_review.md` §3's decision to treat "consecutive"
   as consecutive *fiscal* quarters (so COVID-era filing-deadline relief
   doesn't itself create false gaps).

Neither case removes a firm from the sample permanently — both delay a
firm's entry by a few quarters. Given that IPOs/new listings are a minority
of any given year's cross-section relative to the ~2,000–2,500-company
steady-state population `H11_data_availability_review.md` §4 estimates,
this is expected to reduce the usable event count by a **low-to-mid
single-digit percentage** of the 30,000–60,000 range — not enough to move
the sample out of the "materially larger than H12" comparison that drove
the original sequencing decision (`H11_prioritization_review.md`), but not
zero either.

This is a desk estimate, offered for planning purposes only. The actual
figure will be measured directly and reported as part of the Phase 0 probe
report (item 3 of the current implementation milestone) — before-and-after
counts under both the 5-quarter and 8-quarter thresholds are one of the
report's explicit line items, so this estimate gets replaced with a real
number at the first opportunity rather than relied on further than
necessary.

---

## 6. Approval status

- [x] approved by: vitaliy  date: 2026-08-01

**Approved as written.** `min_seasonal_diffs = 4` (8-quarter minimum
history) is confirmed as the operational threshold and is not to be
adjusted further. Rationale accepted in full: the original 5-quarter floor
was not arithmetically compatible with the pre-registered SUE volatility
calculation; the conflict was discovered through implementation
requirements, not after seeing any result; the change affects measurement
feasibility (how much trailing history is required before SUE can be
computed at all), not the economic hypothesis under test; and the smallest
history window that still supports the pre-specified calculation is
preferable to an unnecessarily longer lookback that would shrink the
sample for no methodological benefit.

The threshold currently coded in `H11Config.min_seasonal_diffs = 4`
(`hypotheses/h11_pead/config.py`, committed at `6474c6d`) required no code
change as a result of this approval — this amendment formalizes a choice
already implemented, per §3 above. Real SEC data collection under H11 may
now proceed on this point.
