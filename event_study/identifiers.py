"""
event_study/identifiers.py -- point-in-time CIK <-> ticker resolution.

Per H11_data_availability_review.md section 5, this is the single highest-
risk mapping in the H11 design -- the same risk category as four prior
mappings in this project (13F CUSIP map, H10's Fed district map, H10b's FDIC
ticker map), every one of which contained at least one real error caught by
an automated gate rather than by reading the output table.

The specific, previously-realized failure mode this module defends against:
H10's regional-bank universe included BRKL, a ticker that was later
*recycled* onto an unrelated company after the original issuer delisted. A
naive "ticker -> CIK" lookup that doesn't account for time will silently
return the wrong company's data for any query dated after the reuse. SEC's
own `company_tickers.json` only gives the *current* ticker per CIK, so
point-in-time resolution requires an explicit valid_from/valid_to history,
built and audited here rather than assumed correct.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


class TickerResolutionError(ValueError):
    """Raised when a CIK<->ticker query can't be resolved unambiguously."""


@dataclass(frozen=True)
class TickerConflict:
    """
    A ticker that maps to more than one CIK with overlapping valid date
    ranges -- the recycled-ticker failure mode, caught before it can
    silently corrupt a downstream join.
    """

    ticker: str
    cik_a: str
    cik_b: str
    overlap_start: pd.Timestamp
    overlap_end: pd.Timestamp


class PointInTimeTickerHistory:
    """
    Wraps a (cik, ticker, valid_from, valid_to, company_name) table and
    resolves ticker <-> CIK queries as of a specific date, rather than
    assuming a ticker means the same company across the whole sample.

    Parameters
    ----------
    history : pd.DataFrame
        Columns: cik (str, zero-padded 10-digit), ticker (str),
        valid_from (Timestamp), valid_to (Timestamp or pd.NaT for "still
        current"), company_name (str). One row per contiguous ticker
        segment -- a CIK that changed ticker once has two rows.
    validate_on_init : bool
        If True (default), runs find_conflicts() at construction time and
        raises TickerResolutionError if any conflict exists. Set False only
        for inspecting a known-bad history (e.g. in a diagnostic script that
        wants to report conflicts rather than crash on them).
    """

    _REQUIRED_COLUMNS = {"cik", "ticker", "valid_from", "valid_to", "company_name"}

    def __init__(self, history: pd.DataFrame, validate_on_init: bool = True):
        missing = self._REQUIRED_COLUMNS - set(history.columns)
        if missing:
            raise ValueError(f"ticker history missing required columns: {missing}")

        self._history = history.copy()
        self._history["cik"] = self._history["cik"].astype(str).str.zfill(10)
        self._history["valid_to"] = self._history["valid_to"].fillna(pd.Timestamp.max)

        if validate_on_init:
            conflicts = self.find_conflicts()
            if conflicts:
                raise TickerResolutionError(
                    f"{len(conflicts)} ticker conflict(s) found in history "
                    f"(recycled-ticker pattern, see BRKL precedent in "
                    f"H10_beige_book_results.md): {conflicts[:3]}"
                    + (" ..." if len(conflicts) > 3 else "")
                )

    def find_conflicts(self) -> list[TickerConflict]:
        """
        Every ticker mapped to more than one CIK with overlapping valid
        date ranges. Called automatically at construction time unless
        validate_on_init=False. This is the check that would have caught
        BRKL before it reached a backtest, had it existed for H10.
        """
        conflicts: list[TickerConflict] = []
        for ticker, group in self._history.groupby("ticker"):
            if len(group) < 2:
                continue
            rows = group.sort_values("valid_from").to_dict("records")
            for i in range(len(rows)):
                for j in range(i + 1, len(rows)):
                    a, b = rows[i], rows[j]
                    if a["cik"] == b["cik"]:
                        continue  # same issuer, e.g. a name change, not a conflict
                    overlap_start = max(a["valid_from"], b["valid_from"])
                    overlap_end = min(a["valid_to"], b["valid_to"])
                    if overlap_start <= overlap_end:
                        conflicts.append(
                            TickerConflict(
                                ticker=ticker,
                                cik_a=a["cik"],
                                cik_b=b["cik"],
                                overlap_start=overlap_start,
                                overlap_end=overlap_end,
                            )
                        )
        return conflicts

    def resolve_cik(self, ticker: str, as_of: pd.Timestamp) -> str:
        """The CIK that `ticker` referred to on date `as_of`."""
        matches = self._history[
            (self._history["ticker"] == ticker)
            & (self._history["valid_from"] <= as_of)
            & (self._history["valid_to"] >= as_of)
        ]
        if matches.empty:
            raise TickerResolutionError(
                f"no CIK found for ticker={ticker!r} as_of={as_of} -- either "
                "not yet listed, already delisted, or missing from history"
            )
        if len(matches) > 1:
            # Should be unreachable if validate_on_init caught conflicts,
            # but checked explicitly rather than silently taking .iloc[0]
            # in case this history was constructed with validate_on_init=False.
            raise TickerResolutionError(
                f"ambiguous: {len(matches)} CIKs match ticker={ticker!r} "
                f"as_of={as_of}: {matches['cik'].tolist()}"
            )
        return str(matches.iloc[0]["cik"])

    def resolve_ticker(self, cik: str, as_of: pd.Timestamp) -> str:
        """The ticker CIK `cik` was trading under on date `as_of`."""
        cik = str(cik).zfill(10)
        matches = self._history[
            (self._history["cik"] == cik)
            & (self._history["valid_from"] <= as_of)
            & (self._history["valid_to"] >= as_of)
        ]
        if matches.empty:
            raise TickerResolutionError(
                f"no ticker found for cik={cik!r} as_of={as_of} -- either "
                "not yet listed, already delisted, or missing from history"
            )
        return str(matches.iloc[0]["ticker"])

    def company_name(self, cik: str, as_of: pd.Timestamp) -> str:
        cik = str(cik).zfill(10)
        matches = self._history[
            (self._history["cik"] == cik)
            & (self._history["valid_from"] <= as_of)
            & (self._history["valid_to"] >= as_of)
        ]
        if matches.empty:
            raise TickerResolutionError(f"no record for cik={cik!r} as_of={as_of}")
        return str(matches.iloc[0]["company_name"])
