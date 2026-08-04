"""
hypotheses/h11_pead/known_at_resolver.py -- resolves a real `known_at` for
EVERY firm-quarter, not just the latest quarter per CIK.

WHY THIS MODULE EXISTS
----------------------
`determine_known_at()` (event_generator.py) implements
H11_PREREGISTRATION.md section 4's rule for a SINGLE firm-quarter, given a
10-Q/10-K timestamp and an optional 8-K Item 2.02 timestamp. Two callers now
need that rule applied across a whole panel:

  - backtests/h11_data_probe.py, which currently applies it inline to one
    quarter per CIK (`firm_eps.index.max()`), and
  - backtests/h11_market_cap_probe.py, whose module docstring flags that it
    deliberately substituted `period_end` for `known_at` and must be
    corrected before feeding a real universe build.

Rather than duplicating the panel-assembly logic in both, it lives here
once: pure, no network, fully unit-testable against fixtures, matching this
project's standing fetch/parse separation.

THIS MODULE IS GOVERNED BY amendments/H11_AMENDMENT_002.md
----------------------------------------------------------
Amendment 002 pins down which observable daily bar operationalizes
"price at `known_at`" for `market_cap`. This module produces the `known_at`
that amendment consumes; it does not itself touch prices.

THREE REAL DEFECTS IN THE PRIOR INLINE IMPLEMENTATION, FIXED HERE
-----------------------------------------------------------------
All three were found by reading h11_data_probe.py's inline block against
the SEC Financial Statement Data Sets schema, not by guessing:

(1) NO FORM FILTER. `sub_all[(cik == ...) & (period == ...)]` matches ANY
    form in sub.txt for that period -- and sub.txt carries 8-K, 20-F, 40-F,
    S-1, 424B*, etc. alongside 10-Q/10-K. A non-periodic form could supply
    the "10-Q" timestamp. Fixed: explicit `PERIODIC_FORMS` filter.

(2) ARBITRARY ROW SELECTION. `.iloc[0]` takes whatever row pandas happens
    to order first, with no sort. Where several filings cover one period
    (an original 10-Q plus a later 10-Q/A, or an overlapping 10-K), the
    selected `filed` date was effectively arbitrary. Fixed: EARLIEST filed
    periodic filing wins -- the as-first-reported principle
    extract_shares_outstanding() already uses for its own tiebreak, and the
    only reading consistent with "when did this become public".

(3) DATE-ONLY `filed` READ AS UTC MIDNIGHT. sub.txt's `filed` is a
    date-only integer (YYYYMMDD). The inline code did
    `pd.to_datetime(filed, format="%Y%m%d", utc=True).tz_convert("US/Eastern")`,
    which places 20200501 at **2020-04-30 20:00 ET** -- the evening of the
    PREVIOUS day. Demonstrated, not theorised:

        >>> pd.to_datetime('20200501', format='%Y%m%d', utc=True).tz_convert('US/Eastern')
        Timestamp('2020-04-30 20:00:00-0400', tz='US/Eastern')

    Consequence: an 8-K Item 2.02 filed the same morning as the 10-Q
    (07:00 ET on 2020-05-01) yields `(tenq_filed - eightk_ts).days == -1`,
    so `determine_known_at`'s `0 <= gap_days` guard rejects it and the event
    silently falls back to the 10-Q -- discarding the primary source the
    pre-registration prefers, and mislabelling the event's provenance.

    This one is NOT unilaterally "fixed" here, because every available
    replacement changes real `known_at` values and therefore entry dates --
    a research-measurement consequence, which under this project's standing
    rule needs an amendment, not a silent code change. What this module does
    instead:

      a. Prefers a REAL `acceptanceDateTime` for the periodic filing when
         one is supplied (`periodic_acceptance_by_cik`), pulled from the same
         submissions API the 8-K path already uses. This is strictly more
         precise and involves no judgement call -- it removes the ambiguity
         rather than resolving it -- so it is a plain engineering
         improvement. It is also the literal reading of pre-registration
         section 4 ("the 10-Q/10-K's own timestamp").
      b. Falls back to sub.txt's date-only `filed` ONLY when no acceptance
         timestamp is available (unavoidable for older filings: the
         submissions API's `filings.recent` block holds only the most recent
         ~1000 filings, so a 2015 10-Q for an active filer will not be in
         it). For that fallback the date-only-to-timestamp convention is an
         explicit, documented parameter, DEFAULTING TO THE EXISTING
         (defective) BEHAVIOUR so that wiring this module in changes no
         research number by itself. See FILED_CONVENTION_* below and the
         draft amendment 003.

    Every row records which path produced its timestamp
    (`disclosure_timestamp_source`), so the real prevalence of the
    date-only fallback is measured in the next real run rather than assumed.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd

from hypotheses.h11_pead.config import H11Config
from hypotheses.h11_pead.event_generator import determine_known_at

# Periodic reports only. Deliberately excludes amendments (/A): an amended
# filing restates a period that was ALREADY made public by the original, so
# treating a 10-Q/A's date as `known_at` would claim the market learned the
# figures later than it did. Where only an amendment is present in the
# pulled window (because the original fell outside it), the period is
# reported by periods_resolvable_only_via_amendment() as a diagnostic rather
# than quietly resolved off the amendment.
PERIODIC_FORMS: tuple[str, ...] = ("10-K", "10-Q", "10-KT", "10-QT")

# How a date-only sub.txt `filed` value is turned into a timestamp when no
# real acceptanceDateTime is available. See defect (3) in the module
# docstring.
#   LEGACY_UTC_MIDNIGHT -- reproduces h11_data_probe.py's existing behaviour
#       exactly (midnight UTC on the filed date, converted to Eastern, i.e.
#       19:00/20:00 ET on the PRIOR calendar day). Known-defective; the
#       default only so that introducing this module is provably
#       number-neutral.
#   EASTERN_END_OF_DAY -- 23:59:59 ET on the filed date. The conservative
#       correction: never claims the filing was knowable earlier in the day
#       than it may have been. Changes entry dates -- requires an approved
#       amendment before it becomes the default.
FILED_CONVENTION_LEGACY_UTC_MIDNIGHT = "legacy_utc_midnight"
FILED_CONVENTION_EASTERN_END_OF_DAY = "eastern_end_of_day"

_PANEL_COLUMNS = [
    "cik",
    "period_end",
    "known_at",
    "event_source",
    "disclosure_filed",
    "disclosure_form",
    "disclosure_adsh",
    "disclosure_timestamp_source",
    "n_periodic_filings_for_period",
]


def _filed_int_to_timestamp(filed_value, convention: str) -> pd.Timestamp:
    """
    sub.txt `filed` is YYYYMMDD (int or str). Returns a tz-aware US/Eastern
    Timestamp under the named convention. Raises on an unknown convention
    rather than silently defaulting -- a typo'd convention string must not
    quietly reinstate the defective reading.
    """
    raw = str(int(filed_value))
    if convention == FILED_CONVENTION_LEGACY_UTC_MIDNIGHT:
        return pd.to_datetime(raw, format="%Y%m%d", utc=True).tz_convert("US/Eastern")
    if convention == FILED_CONVENTION_EASTERN_END_OF_DAY:
        naive = pd.to_datetime(raw, format="%Y%m%d") + pd.Timedelta(hours=23, minutes=59, seconds=59)
        return naive.tz_localize("US/Eastern")
    raise ValueError(
        f"unknown filed_date_convention {convention!r} -- expected one of "
        f"{FILED_CONVENTION_LEGACY_UTC_MIDNIGHT!r}, {FILED_CONVENTION_EASTERN_END_OF_DAY!r}"
    )


def _periodic_filings(sub_df: pd.DataFrame, forms: Sequence[str]) -> pd.DataFrame:
    """
    Filters sub.txt to periodic reports with a usable (cik, period, filed)
    and normalises cik to a 10-padded string. Returns an empty, correctly
    typed frame rather than raising when nothing survives -- an empty
    quarter is an ordinary outcome, not an invariant violation.
    """
    needed = {"adsh", "cik", "form", "period", "filed"}
    missing = needed - set(sub_df.columns)
    if missing:
        raise ValueError(f"sub_df missing required columns: {sorted(missing)}")

    if sub_df.empty:
        return sub_df.assign(_cik_padded=pd.Series(dtype="object")).iloc[0:0]

    df = sub_df[sub_df["form"].isin(list(forms))].copy()
    df = df[df["period"].notna() & df["filed"].notna()]
    if df.empty:
        return df.assign(_cik_padded=pd.Series(dtype="object"))
    df["_cik_padded"] = df["cik"].apply(lambda c: str(int(c)).zfill(10))
    return df


def periods_resolvable_only_via_amendment(
    sub_df: pd.DataFrame, forms: Sequence[str] = PERIODIC_FORMS
) -> pd.DataFrame:
    """
    Diagnostic, not a filter. Returns the (cik, period) pairs for which the
    pulled sub.txt contains an amended periodic report (10-Q/A, 10-K/A) but
    NO original. Those periods are absent from resolve_known_at_panel()'s
    output by design; this surfaces how many there are so the attrition is
    counted rather than invisible.
    """
    base = set(forms)
    amended = {f"{f}/A" for f in base}
    if sub_df.empty or "form" not in sub_df.columns:
        return pd.DataFrame(columns=["cik", "period"])

    df = sub_df[sub_df["form"].isin(base | amended)].copy()
    if df.empty:
        return pd.DataFrame(columns=["cik", "period"])
    df["_cik_padded"] = df["cik"].apply(lambda c: str(int(c)).zfill(10))
    df["_is_base"] = df["form"].isin(base)

    grouped = df.groupby(["_cik_padded", "period"], as_index=False)["_is_base"].any()
    only_amended = grouped[~grouped["_is_base"]]
    return only_amended.rename(columns={"_cik_padded": "cik"})[["cik", "period"]].reset_index(drop=True)


def resolve_known_at_panel(
    sub_df: pd.DataFrame,
    item202_by_cik: Mapping[str, pd.DataFrame],
    config: H11Config,
    periodic_acceptance_by_cik: Mapping[str, pd.DataFrame] | None = None,
    ciks: Sequence[str] | None = None,
    forms: Sequence[str] = PERIODIC_FORMS,
    filed_date_convention: str = FILED_CONVENTION_LEGACY_UTC_MIDNIGHT,
) -> pd.DataFrame:
    """
    Applies H11_PREREGISTRATION.md section 4's known_at rule to every
    (cik, period_end) present in `sub_df` as a periodic report.

    sub_df : concatenated sub.txt frames from
        data_connectors.sec_financial_statement_datasets.fetch_quarter.
        Requires columns adsh, cik, form, period, filed.
    item202_by_cik : {10-padded cik -> DataFrame from
        parse_submission_filings_for_item_202}, i.e. with a tz-aware
        US/Eastern `acceptance_datetime`. A CIK absent from this mapping is
        treated as "no 8-K information available", which resolves to the
        10-Q fallback -- identical to having zero qualifying 8-Ks. That
        conflation is deliberate and matches h11_data_probe.py's existing
        behaviour on a failed fetch, where the miss is counted separately in
        `historical_item202_counts` rather than inferred from this panel.
    periodic_acceptance_by_cik : optional {10-padded cik -> DataFrame with
        columns accession_number and acceptance_datetime (tz-aware
        Eastern)}. When a periodic filing's accession number is found here,
        its real acceptance timestamp is used instead of the date-only
        sub.txt `filed` -- see defect (3) in the module docstring.
    ciks : optional whitelist of CIKs (any zero-padding) to resolve. REQUIRED
        IN PRACTICE whenever `item202_by_cik` covers fewer CIKs than
        `sub_df` does, which is the normal case for a probe: sub.txt is a
        whole-population bulk file, while 8-K submissions are fetched
        per-CIK. Resolving the full population against 8-K data that exists
        for only a handful of CIKs does not merely waste work -- it makes
        the `event_source` breakdown actively misleading, because every CIK
        with no fetched 8-K data resolves to "10q_fallback" and swamps the
        counts for the CIKs actually under study. This parameter exists
        because exactly that happened on the first real run: 67,447
        "10q_fallback" against 19 "8k_item202", which reads as "the primary
        source almost never fires" when the truth for the 3 CIKs with real
        8-K data was 19 of 32 (59%). None means resolve everything, and is
        correct only when 8-K coverage genuinely spans sub_df.
    forms : periodic forms to consider. Amendments excluded by default.
    filed_date_convention : how a date-only `filed` becomes a timestamp when
        no acceptance timestamp exists. Defaults to the existing behaviour;
        do not change without an approved amendment.

    Returns one row per (cik, period_end) with columns:
        cik, period_end, known_at, event_source, disclosure_filed,
        disclosure_form, disclosure_adsh, disclosure_timestamp_source,
        n_periodic_filings_for_period

    `known_at` is tz-aware US/Eastern. `period_end` is tz-naive (it is a
    reporting-period boundary, not an instant). Callers joining `known_at`
    against a tz-naive daily price panel must convert explicitly -- see
    data_connectors.market_data_yfinance.last_printed_close, which does.

    Rows are NOT produced for periods with no original periodic filing in
    `sub_df`; a caller joining shares-outstanding rows to this panel must
    count its unmatched rows as explicit attrition with a stated reason,
    never drop them silently.
    """
    periodic = _periodic_filings(sub_df, forms)
    if ciks is not None:
        wanted = {str(int(c)).zfill(10) for c in ciks}
        periodic = periodic[periodic["_cik_padded"].isin(wanted)]
    if periodic.empty:
        return pd.DataFrame(columns=_PANEL_COLUMNS)

    # Earliest-filed original wins. Sorting on (filed, adsh) makes the
    # choice deterministic even for the pathological case of two filings
    # bearing the same filed date -- an arbitrary-but-stable tiebreak is
    # still strictly better than .iloc[0] on an unsorted frame, and the
    # duplicate is visible via n_periodic_filings_for_period.
    periodic = periodic.sort_values(["_cik_padded", "period", "filed", "adsh"])
    counts = (
        periodic.groupby(["_cik_padded", "period"], as_index=False)
        .size()
        .rename(columns={"size": "n_periodic_filings_for_period"})
    )
    chosen = periodic.groupby(["_cik_padded", "period"], as_index=False).first()
    chosen = chosen.merge(counts, on=["_cik_padded", "period"], how="left")

    rows = []
    for _, filing in chosen.iterrows():
        cik = filing["_cik_padded"]
        period_end = pd.to_datetime(str(int(filing["period"])), format="%Y%m%d", errors="coerce")
        if pd.isna(period_end):
            continue

        acceptance = _lookup_acceptance(periodic_acceptance_by_cik, cik, filing["adsh"])
        if acceptance is not None:
            disclosure_ts = acceptance
            ts_source = "submissions_acceptance_datetime"
        else:
            disclosure_ts = _filed_int_to_timestamp(filing["filed"], filed_date_convention)
            ts_source = f"sub_txt_filed_date:{filed_date_convention}"

        eightk_ts = _best_matching_item202(item202_by_cik.get(cik), disclosure_ts, config)
        known_at, source = determine_known_at(disclosure_ts, eightk_ts, config)

        rows.append(
            {
                "cik": cik,
                "period_end": period_end,
                "known_at": known_at,
                "event_source": source,
                "disclosure_filed": disclosure_ts,
                "disclosure_form": filing["form"],
                "disclosure_adsh": filing["adsh"],
                "disclosure_timestamp_source": ts_source,
                "n_periodic_filings_for_period": int(filing["n_periodic_filings_for_period"]),
            }
        )

    if not rows:
        return pd.DataFrame(columns=_PANEL_COLUMNS)
    return pd.DataFrame(rows)[_PANEL_COLUMNS].reset_index(drop=True)


def _lookup_acceptance(
    periodic_acceptance_by_cik: Mapping[str, pd.DataFrame] | None, cik: str, adsh: str
) -> pd.Timestamp | None:
    """
    Real acceptanceDateTime for one periodic filing, or None. Returns None
    (never a guessed or coerced value) when the CIK, the accession number,
    or the timestamp itself is absent -- the caller then falls back to the
    date-only path and records that it did so.
    """
    if not periodic_acceptance_by_cik:
        return None
    frame = periodic_acceptance_by_cik.get(cik)
    if frame is None or frame.empty or "accession_number" not in frame.columns:
        return None
    hit = frame[frame["accession_number"] == adsh]
    if hit.empty:
        return None
    value = hit.iloc[0].get("acceptance_datetime")
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value)


def _best_matching_item202(
    item202: pd.DataFrame | None, disclosure_ts: pd.Timestamp, config: H11Config
) -> pd.Timestamp | None:
    """
    The LATEST 8-K Item 2.02 acceptance timestamp at or before
    `disclosure_ts` and within `config.fallback_window_days` of it -- the
    same selection h11_data_probe.py made inline, preserved exactly so
    wiring this module in is behaviour-neutral on that point.

    Latest-in-window (not earliest) is correct: where a filer issues more
    than one Item 2.02 8-K before its 10-Q, the one immediately preceding
    the periodic report is the earnings release the 10-Q confirms; an
    earlier one in the same window is more likely a prior period's or a
    guidance update. determine_known_at() then re-checks the window itself,
    so the two guards agree by construction rather than by coincidence.
    """
    if item202 is None or item202.empty or "acceptance_datetime" not in item202.columns:
        return None
    window_start = disclosure_ts - pd.Timedelta(days=config.fallback_window_days)
    matching = item202[
        (item202["acceptance_datetime"] <= disclosure_ts) & (item202["acceptance_datetime"] >= window_start)
    ]
    if matching.empty:
        return None
    return matching["acceptance_datetime"].max()
