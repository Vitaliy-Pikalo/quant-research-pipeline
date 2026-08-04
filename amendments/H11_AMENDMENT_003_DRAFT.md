# H11 Amendment 003 (DRAFT) — timestamp convention for a date-only periodic `filed` date

**Status: DRAFT, NOT PROPOSED FOR APPROVAL YET, NOT IMPLEMENTED.** Filed as
a draft rather than a proposal because the right decision depends on a real
number this project does not yet have: how often the date-only fallback path
is actually taken. That number is produced by the next real probe run. No
return, IC, Sharpe, or p-value depends on this.

---

## 1. The defect

`backtests/h11_data_probe.py` converted the SEC Financial Statement Data
Sets' `filed` field — a **date-only** integer, `YYYYMMDD`, with no time
component — into a timestamp like this:

```python
pd.to_datetime(tenq_rows.iloc[0]["filed"], format="%Y%m%d", utc=True).tz_convert("US/Eastern")
```

Reading a date-only value as **midnight UTC** and then converting to Eastern
moves it backwards across the date line:

```
>>> pd.to_datetime('20200501', format='%Y%m%d', utc=True).tz_convert('US/Eastern')
Timestamp('2020-04-30 20:00:00-0400', tz='US/Eastern')
```

A 10-Q filed on 2020-05-01 is placed at **20:00 ET on 2020-04-30**. This is
not a defensible reading of the field under any convention — it is a plain
misinterpretation, demonstrated above rather than argued.

## 2. Why it matters, concretely

`determine_known_at()` prefers an 8-K Item 2.02 timestamp only when
`0 <= (periodic_timestamp - eightk_timestamp).days <= fallback_window_days`.
With the periodic timestamp displaced to the prior evening, an 8-K accepted
the **same morning** as the 10-Q produces `gap_days == -1`, fails the
`0 <= gap_days` guard, and the event silently falls back to the 10-Q — losing
the primary source the pre-registration prefers **and** mislabelling the
event's provenance in `event_source`, which §4.2 requires to be accurate.

Verified as a live behaviour, not inferred:
`tests/test_known_at_resolver.py::TestDateOnlyFiledConvention::test_same_morning_8k_is_recovered_once_a_real_acceptance_timestamp_exists`
asserts the fallback under the legacy convention and the correct 8-K
selection once a real acceptance timestamp is supplied.

Secondary effect: the pre-registration §6 entry rule keys off 16:00 ET, so a
20:00-ET-prior-day `known_at` yields the *filing date's* close as the entry
bar — i.e. it behaves as though the filing was always knowable before that
day's close, which for a post-16:00 filing it was not.

## 3. What has already been done without an amendment (and why that was legitimate)

`hypotheses/h11_pead/known_at_resolver.py` now prefers the periodic filing's
**real `acceptanceDateTime`** from the SEC submissions API — the same field
the 8-K path has always used — via
`sec_8k_item202.parse_submission_filings_for_periodic()`. Where that is
available the ambiguity does not need resolving; it disappears. Substituting
a precise real timestamp for a guessed one is an engineering improvement, not
a research-definition change, and is also the literal reading of
pre-registration §4 ("the 10-Q/10-K's own timestamp"), so it ships without an
amendment per the standing division of labour.

**No amendment is required for that part, and this draft does not propose
one.**

## 4. What still needs deciding

The submissions API's `filings.recent` block holds only the most recent
filings (documented as roughly the last 1000, or one year, whichever is
larger). Older filings live in separate `filings.files` archives that the
connector does not currently fetch. **For a 2015–2025 build, many older
periodic filings will therefore have no acceptance timestamp available**, and
the date-only `filed` fallback is unavoidable for them.

For those rows, a convention must be chosen:

| option | timestamp for `filed = 20200501` | consequence |
|---|---|---|
| **legacy** (current default) | 2020-04-30 20:00 ET | known-defective; rejects same-day 8-Ks; entry on the filing date's close |
| **Eastern end of day** | 2020-05-01 23:59:59 ET | never claims earlier knowledge than it had; entry on the NEXT trading day; accepts same-day 8-Ks |
| **Eastern midnight** | 2020-05-01 00:00 ET | claims the filing was public before the market opened — usually false, and look-ahead |
| **fetch the archives** | real timestamp | no convention needed; costs a second request tier per CIK and real implementation work |

`known_at_resolver.py` exposes this as an explicit
`filed_date_convention` parameter with `FILED_CONVENTION_LEGACY_UTC_MIDNIGHT`
as the **default**, precisely so that introducing the module changes no
research number by itself. An unrecognised value raises rather than silently
defaulting.

## 5. Why this is a draft and not yet a proposal

Choosing between "Eastern end of day" and "fetch the archives" turns on how
many firm-quarters actually land on the fallback path. If the fallback is
rare, the convention barely matters and the cheap fix is right; if it covers
most of 2015–2020, the convention silently governs the majority of the sample
and the archive fetch is worth building.

That count is not estimated here. Every row emitted by the probe now carries
`disclosure_timestamp_source`, so the next real run measures it directly.
**This draft is completed and submitted for approval only after that number
exists** — consistent with this project's real-data-first rule that analysis
follows real output rather than preceding it.

## 6. Interim status

- The legacy convention remains the default and is therefore still in force
  for any row without a real acceptance timestamp. It is **known-defective**
  and is retained solely to keep the resolver's introduction number-neutral,
  not because it is correct.
- No result of any kind currently depends on it.
- It must not survive into the full 2015–2025 build unexamined. This draft is
  the record that it is a known open item rather than an accepted behaviour.
