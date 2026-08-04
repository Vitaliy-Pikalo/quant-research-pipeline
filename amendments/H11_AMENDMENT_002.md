# H11 Amendment 002 — which observable daily bar operationalizes "price at `known_at`" for `market_cap`

**Status: APPROVED (2026-08-04). No return, IC, Sharpe, or p-value has been
computed under this design. The real data pulled to date is confined to
shares-outstanding / market-cap plumbing validation on 3 verified CIKs; no
result of any kind depended on the choice made here at the time it was
made — the decision was taken before the first `known_at`-based probe run,
not after seeing its output.**

This amendment does not modify `results/H11_PREREGISTRATION.md` or
`results/H11_IMPLEMENTATION_SPEC.md`. Per this project's standing rule, the
frozen pre-registration is never silently edited — any deviation or
ambiguity discovered during implementation is recorded here, separately,
with a reason, and applied in code only after this document is approved.

---

## 1. The ambiguity

`H11_IMPLEMENTATION_SPEC.md` §3 defines the two market-data-derived fields
carried on every event:

| field | spec text |
|---|---|
| `market_cap` | "at `known_at`, used by stage 4's quintile bucketing" |
| `adv_20d` | "20-day median dollar ADV **as of the day before** `known_at`, used by stage 5" |

`adv_20d` is unambiguous and already correctly implemented:
`trailing_median_dollar_adv()` takes the window **strictly before** its
`as_of` argument, so passing `known_at` yields exactly what §3 asks for.
Nothing in this amendment touches `adv_20d`.

`market_cap` is not unambiguous. `known_at` is an EDGAR accession timestamp
precise to the second (`acceptanceDateTime`, converted to US/Eastern — see
`data_connectors/sec_8k_item202.py`). This project's only price source is
free daily bars from Yahoo Finance (`data_connectors/market_data_yfinance.py`);
`H11_data_availability_review.md` records that no free intraday source
survived evaluation. **There is therefore no observable price at `known_at`
itself.** A daily close is a 16:00 ET print; an 8-K Item 2.02 filed at, say,
09:15 ET has no contemporaneous observable price at all, and the same-day
close does not yet exist at that moment.

So "price at `known_at`" must be operationalized as one of several daily
bars, and the candidates differ in a way that matters to this project
specifically — because one of them introduces look-ahead into a **selection
filter**, and the avoidance of exactly that class of error is the stated
reason this project exists (`H11_PREREGISTRATION.md` §6;
`results/POST_bugs_that_produce_results.md`).

This was discovered while wiring the real `known_at` into
`backtests/h11_market_cap_probe.py`, which had until now deliberately
substituted `period_end` for `known_at` and flagged that substitution in its
own module docstring as requiring correction before feeding a real universe
build. It is raised here rather than resolved silently in the probe, per the
standing rule that a methodology-affecting ambiguity found mid-implementation
gets an amendment, not a code comment alone. Amendment 001 resolved a
structurally identical case (§3's "5 consecutive quarters" vs §5's SUE
formula) the same way.

---

## 2. Original specification

`H11_IMPLEMENTATION_SPEC.md` §3, `market_cap` row: **"at `known_at`"**.
This text is unchanged in the frozen document and remains the text of
record. This amendment proposes a superseding *operational* definition for
implementation purposes only — it does not redefine what `market_cap` means,
only which observable bar stands in for an unobservable instant.

---

## 3. The candidates

Let `known_at` be a tz-aware US/Eastern timestamp, and let the price panel be
daily bars on real trading days.

| # | candidate | look-ahead in the cap-band filter? | is it the bar actually traded at? |
|---|---|---|---|
| A | the last close that had **actually printed** at `known_at` — same-day close if `known_at` ≥ 16:00 ET, else the prior trading day's close | none | only when `known_at` is post-close |
| B | the **entry** close (`determine_entry_date` rule: same-day close if `known_at` < 16:00 ET, else next trading day's close) | yes, for any pre-16:00 `known_at` | yes, by construction |
| C | last close on or before `known_at`'s **calendar date** | yes, for any pre-16:00 `known_at` | only coincidentally |

Candidate C is dismissed without further argument: it is look-ahead for a
pre-16:00 filing *and* not the entry bar for a post-16:00 filing, so it
carries the cost of both alternatives and the justification of neither. It
is listed only because it is the most naive reading of the spec text and
would be the likeliest silent default if this decision were left
unrecorded.

---

## 4. Proposed operational definition

**Adopt candidate A: `market_cap` = `shares_outstanding` × the close of the
last daily bar that had actually printed at `known_at`** — i.e. the same-day
close when `known_at` falls at or after the 16:00 ET close, and the previous
trading day's close otherwise.

Note this is stronger than a blanket "strictly before `known_at`" rule, and
deliberately so. For a filing accepted at 18:30 ET, that day's close is
genuinely observable, and discarding it would introduce a *backwards* error
(measuring the firm on stale information) to avoid a forwards one. Rule A as
stated is not a conservative approximation of "price at `known_at`": for a
daily panel it is the exact set of price information observable at that
instant. Implemented as `market_data_yfinance.last_printed_close()`.

Where no such bar exists (a firm that had not yet listed under the resolved
ticker, or a price series that does not reach back far enough), `market_cap`
is `None` and the firm-quarter is recorded as a **disqualification with a
stated reason** — never zero, never dropped silently — matching the existing
contract in `price_as_of()`'s docstring and the attrition-accounting
discipline already used throughout stages 0–2.

### Why A over B

1. **`market_cap` is used as a selection filter, and a selection filter must
   run on information available at the decision instant.** Stage 2 uses
   `market_cap` to decide whether a firm-quarter enters the universe at all
   ($50M–$2B cap band); stage 4 uses it for quintile bucketing. Under B, a
   firm-quarter filed at 09:15 ET is admitted or rejected using a price that
   prints at 16:00 that same day — the strategy would be conditioning
   membership on a bar that had not occurred when the decision was
   nominally made. The magnitude is small (one day of price movement), but
   the *kind* of error is precisely the kind this project's entire rigor
   stack exists to eliminate, and small-magnitude look-ahead near an
   earnings announcement is not obviously small: the announcement-day move
   is the single largest expected price jump in the event window, so it is
   the worst possible day on which to accept a "it's only one bar" argument.

2. **A cannot be gamed by the boundary; B can.** Under B, the cap-band
   decision for a pre-16:00 filer partially incorporates the market's
   reaction to the very earnings surprise being measured. A firm whose
   announcement drove it across the $2B ceiling would be excluded on the
   strength of its own event-day move. That is a mechanical correlation
   between the selection filter and the outcome variable — the textbook
   generator of a spurious result, and worse than a mere timing
   imprecision.

3. **A is internally consistent with `adv_20d`.** §3 already specifies
   `adv_20d` strictly before `known_at`. Reading `market_cap` the same way
   makes both universe-qualification inputs measured on the same side of the
   event, rather than one before it and one after.

4. **The cost of A is real but confined and does not touch returns.**
   `market_cap` under A is measured on a different bar than the entry price
   under `H11_PREREGISTRATION.md` §6. That is accepted deliberately: §6
   governs *entry execution* and is unchanged by this amendment, while §3's
   `market_cap` governs *universe membership and bucketing*. These are
   separate questions and there is no requirement in either frozen document
   that they share a bar. **No return, benchmark, or cost calculation reads
   `market_cap`** — entry, holding-period return, and matched-control
   construction all use the price panel directly. So A cannot bias a
   measured return; its only effect is on which firm-quarters are in the
   sample and which quintile they land in.

---

## 5. What this does not change

- `H11_PREREGISTRATION.md` §4 (event definition), §5 (SUE), §6 (4pm-ET
  entry rule), §7 (benchmark), §9 (cost model), §11 (test list), §12
  (decision rule): all unaffected verbatim.
- `adv_20d`: unaffected; already strictly-before-`known_at` and already
  implemented that way.
- `determine_entry_date()`: unaffected. Entry is still the §6 rule. This
  amendment explicitly does **not** propose using bar A for entry.
- The cap band itself ($50M–$2B): unaffected. Only the timestamp at which a
  firm is measured against it is being pinned down.
- `EPS_TAG_PRIORITY` / `extract_eps_records()` / `custom_tag_fallback_rate()`:
  untouched, still governed by the separate deferred decision recorded in
  `docs/H11_EPS_TAG_ANALYSIS.md`.

This is a **measurement-timing precision** change — which observable stands
in for an unobservable instant — not a change to what is measured, how it is
used, or what outcome is predicted. `H11_PREREGISTRATION.md` §14's
commitment to *not* search over specification choices is preserved: this
amendment fixes one operational reading in advance of the full build and
commits to it, rather than leaving a degree of freedom open to be resolved
later against results.

---

## 6. Expected sample-size impact

**Expected to be near zero, and this is a testable claim, not an assertion.**

A and B differ by at most one trading day of price movement. A firm-quarter's
qualification changes only if that single day's move carries it across the
$50M or $2B boundary. Structurally that requires the firm to sit within a few
percent of a band edge *and* to have a large announcement-day move in the
direction that crosses it.

The honest complication: earnings-announcement days carry unusually large
moves for exactly the population this design targets, so the per-affected-firm
probability is higher than a random-day comparison would suggest. The
countervailing point is that the affected set is only firms already sitting
near a band edge, which is a small slice of the cross-section.

No number is estimated here. **The A-vs-B disagreement count will be measured
directly and reported**: the probe will compute qualification under both
readings and report how many firm-quarters differ. That measurement is a
diagnostic on a decision already made in advance — it is explicitly **not** a
basis for switching to whichever reading yields more events. If the count is
material, that is a fact to document about the sample's sensitivity, not a
reason to revisit this choice.

---

## 7. Implementation consequences if approved

1. `hypotheses/h11_pead/known_at_resolver.py` (new, pure/offline-testable):
   resolves `(cik, period_end) → (known_at, event_source)` for every
   firm-quarter, not just the latest one per CIK as
   `backtests/h11_data_probe.py` currently does.
2. `backtests/h11_market_cap_probe.py`: joins that panel and replaces the
   `period_end` substitution flagged in its own docstring with real
   `known_at`; `price_as_of()` is called with the bar-A rule and output
   columns are renamed off `_as_of_period_end`.
3. `known_at` is tz-aware US/Eastern; the price panel's `date` column is
   tz-naive. The comparison is made explicit and tested (including across a
   DST boundary) rather than left to pandas coercion — an implicit
   tz-comparison here is the same failure mode as the already-fixed
   `acceptanceDateTime` UTC→Eastern bug.
4. Firm-quarters with no resolvable `known_at` (no 10-Q/10-K row for the
   period) are counted as explicit attrition with a stated reason, never
   silently dropped.

Items 1–4 are **not** to be implemented before this amendment is approved.

Separately and **not** gated on this approval: `backtests/h11_data_probe.py`
selects its 10-Q row via `.iloc[0]` with no form filter and no ordering by
filed date, so it can select a non-periodic form or an arbitrary amendment
rather than the earliest-filed periodic report. That is a plain engineering
bug, not a research-definition change, and ships immediately in its own
atomic commit per the standing division between the two.

---

## 8. Approval status

- [x] approved by: vitaliy  date: 2026-08-04

**Approved as written.** Candidate A — `market_cap` = `shares_outstanding` ×
the close of the last daily bar that had actually printed at `known_at` — is
confirmed as the operational definition and is not to be adjusted further.
Rationale accepted in full: `market_cap` governs universe membership and
quintile bucketing, both selection decisions, and a selection decision must
not condition on a bar that had not printed when it was nominally made;
the boundary case (a filer pushed across the $2B ceiling by its own
announcement-day move) is a mechanical correlation between the filter and
the outcome variable rather than a rounding-level timing imprecision; and no
return, benchmark, or cost calculation reads `market_cap`, so the choice
cannot bias a measured return in either direction.

Candidate B is recorded as the considered-and-rejected alternative. It
remains computed, as `price_entry_bar_diagnostic_only`, solely to satisfy
§6's commitment to **measure** the A-vs-B disagreement rather than estimate
it. That measurement is a fact to report about the sample's sensitivity. It
is explicitly **not** grounds for revisiting this decision, whatever it turns
out to be.

The implementation described in §7 was written against this amendment before
approval and is committed only now that approval exists
(`data_connectors/market_data_yfinance.last_printed_close`,
`hypotheses/h11_pead/known_at_resolver`,
`backtests/h11_market_cap_probe`). The engineering fixes listed at the end of
§7 shipped separately and ahead of this approval, per the standing division
between engineering fixes and research-definition changes.

Real `known_at`-based data collection under H11 may now proceed on this
point.
