# H11 Amendment 004 (DRAFT) — firm-quarters whose only periodic filing in range is an amendment

**Status: DRAFT, written from real output, NOT APPROVED, NOT IMPLEMENTED.**
No return, IC, Sharpe, or p-value depends on this. Raised because the first
real `known_at`-based probe run dropped a firm-quarter that should probably
produce an event, and the current behaviour — while correct as documented —
resolves the wrong question.

---

## 1. The real observation

`backtests/h11_market_cap_probe.py`'s first `known_at` run emitted 12
shares-outstanding rows with no resolvable `known_at`. Eleven were expected:
`is_own_reporting_period=False`, i.e. comparative echoes of 2017–2019 periods
predating the pulled window. The twelfth was not:

```
cik 798081 (Lakeland Industries), period_end 2020-07-31,
is_own_reporting_period=True, implausible_jump_flag=True
```

`backtests/_diag_missing_known_at.py`, run live against 2020q3 + 2020q4,
returned the reason directly rather than by inference:

```
                adsh   form   period     fy fp    filed _source_quarter
0001654954-20-010056 10-Q/A 20200731 2021.0 Q2 20200914          2020q3

forms present : ['10-Q/A']
forms the resolver accepts: NONE
```

**The only periodic filing for that period anywhere in the pulled data is an
amendment.** The original 10-Q is absent from the Financial Statement Data
Sets for the quarter in which it must have been filed.

Two further facts, both read off real output rather than assumed:

1. `is_own_reporting_period=True` means the shares-outstanding value for this
   firm-quarter was taken **from the 10-Q/A itself** — and that value is the
   known 1000×-too-high figure found in the previous session. The amendment
   carries the error. Whether the original 10-Q also carried it, and whether
   the amendment was filed *because* of it, is not established by this
   output and is not claimed here.
2. Lakeland files Item 2.02 8-Ks routinely — 8 of its other 10 quarters in
   this window resolved to `8k_item202`. So for this firm-quarter an 8-K
   earnings release very likely exists and would supply a **better**
   `known_at` than any 10-Q date.

## 2. Why the current behaviour is right about the wrong question

`known_at_resolver.PERIODIC_FORMS` excludes `/A` forms deliberately: an
amendment restates a period the original already made public, so treating the
amendment's date as `known_at` would claim the market learned the figures
weeks later than it did. **That reasoning is sound and this draft does not
propose changing it.**

But the resolver applies that exclusion by dropping the **period**, not just
the filing. The consequence is a false dichotomy:

| current options | effect |
|---|---|
| use the 10-Q/A's date | `known_at` biased **late** by the amendment lag (here, unknown but ≥ days) |
| drop the firm-quarter | a real earnings event, with a real 8-K, silently absent from the sample |

Neither is right, and the second is what currently happens. A `known_at`
biased late is not a look-ahead error — it is the safe direction — but it is
still corrupting: entry would land after the announcement move the hypothesis
exists to measure, systematically understating drift for exactly these
firm-quarters. Dropping them instead removes them from the sample on a
criterion (whether an original filing happens to appear in the bulk file)
that has no relationship to the hypothesis.

**Population-wide count from the same run: 460 periods present only as an
amendment.** Against ~67,466 resolved (cik, period_end) pairs that is ~0.7%.
Small, but not nil, and — importantly — **not randomly distributed**: filers
who amend are plausibly correlated with filers who have messy XBRL, which is
precisely the small-cap population this design targets. The one instance we
have looked at is also the one instance in this probe with a known filer
tagging error. One case is not evidence of a pattern, and this draft does not
treat it as such; it is a reason to measure rather than to assume the 0.7% is
random.

## 3. Proposed direction (not yet a proposal for approval)

**Stop dropping the period. Resolve `known_at` for it from the best available
source, in this priority order, and flag the provenance:**

1. **8-K Item 2.02** within the pre-registered fallback window before the
   original filing — already the preferred source under
   `H11_PREREGISTRATION.md` §4, and unaffected by which 10-Q variant landed in
   the bulk file. For Lakeland's case this is likely to resolve it outright.
2. **The original periodic filing's `acceptanceDateTime` from the submissions
   API.** The submissions endpoint lists *all* forms, including originals
   absent from the Financial Statement Data Sets, so the original's real
   timestamp is very likely recoverable even when its FSDS row is not. This
   costs no extra request — the payload is already fetched per CIK.
3. **The amendment's own date, flagged**, as an explicit last resort with
   `event_source` recording it, so any such event can be excluded from a
   robustness re-run rather than being indistinguishable from a clean one.

Step 2 is the substantive claim and it is **unverified**: it needs a real run
confirming the original 10-Q appears in Lakeland's submissions payload for
this period. That check is cheap and should precede any implementation.

## 4. Why this is a draft

Three things are missing before this becomes a proposal:

1. **Confirmation that step 2 works** — does the original 10-Q for
   (798081, 2020-07-31) appear in the submissions API with a real
   `acceptanceDateTime`? Real check, not reasoning.
2. **Whether step 1 alone suffices.** If an Item 2.02 8-K resolves most of the
   460, the fallback chain barely matters and the change is small.
3. **Whether the 460 are randomly distributed or concentrated.** If
   amendment-only periods cluster in the small-cap tail, a 0.7% exclusion is
   not a 0.7% effect on the hypothesis.

None of that is estimated here. All three come from real runs.

## 5. Interim status

Current behaviour — drop the period, count it, do not patch — **stands**. It
is conservative (an absent event cannot produce a false positive) and it is
visible (the count is printed every run). It is recorded here as a **known
open item**, not an accepted design.

This must be resolved before the full 2015–2025 build, where 0.7% of a
90,000–110,000 firm-quarter population is several hundred real events.
