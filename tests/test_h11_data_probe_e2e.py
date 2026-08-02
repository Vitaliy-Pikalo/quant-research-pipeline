"""
tests/test_h11_data_probe_e2e.py -- dry-run of backtests/h11_data_probe.py's
probe() orchestrator with every network call replaced by a fixture,
end to end, no real SEC access.

backtests/h11_data_probe.py itself had never actually been executed before
this test was written -- only syntax-checked (py_compile/ast.parse), since
this sandbox cannot reach data.sec.gov. That gap matters: a script can be
syntactically valid and still fail on its first real run for reasons no
syntax check catches (a wrong DataFrame column name, a dict-key typo, an
off-by-one in a date filter). This test closes that gap as far as it can be
closed without real network access -- it runs the actual `probe()` function,
with `fetch_submission`, `fetch_quarter`, and `fetch_item_202_filings`
monkeypatched to return realistic-shaped fixture data instead of making a
live call, and asserts the whole pipeline completes and produces sane
output files. It does NOT validate that SEC's live response actually
matches this fixture's assumed shape -- that remains the job of the first
real local run, per sec_8k_item202.py's HONESTY FLAG.

Fixture covers three distinct outcomes deliberately, to exercise more than
the "everything works" path:
  - CIK 1: resolves fully, 8 quarters of EPS history, a qualifying 8-K
    Item 2.02 within the fallback window -> produces one Event via the
    primary (8-K) source.
  - CIK 2: fetch_submission AND fetch_item_202_filings both raise (a
    network/lookup failure) -> counted as a ticker-resolution failure and,
    separately, as having no EPS records (no fixture data was ever
    supplied for this CIK), not silently skipped.
  - CIK 3: resolves fine but has only 2 quarters of EPS history -> SUE
    cannot be computed (insufficient_history_for_any_seasonal_diff),
    exercising a distinct, correctly-labeled attrition reason.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

import backtests.h11_data_probe as h11_data_probe
from data_connectors.sec_8k_item202 import parse_submission_filings_for_item_202


def _cik1_sub_num_rows() -> tuple[list[dict], list[dict]]:
    """One 10-Q filing (single adsh) whose XBRL comparative-period facts
    supply 8 trailing quarters of diluted EPS -- realistic in that a single
    10-Q's XBRL instance commonly tags both the current and prior-year
    comparative period, not a simplification unique to this fixture."""
    adsh = "0000000001-23-000009"
    sub = [dict(adsh=adsh, cik=1, form="10-Q", period=20230930, fy=2023, fp="Q3", filed=20231102)]
    quarters_ends = pd.date_range("2021-12-31", periods=8, freq="QE")
    num = [
        dict(adsh=adsh, tag="EarningsPerShareDiluted", version="us-gaap/2023", ddate=int(d.strftime("%Y%m%d")), qtrs=1, uom="USD/shares", value=0.50 + 0.03 * i)
        for i, d in enumerate(quarters_ends)
    ]
    return sub, num


def _cik3_sub_num_rows() -> tuple[list[dict], list[dict]]:
    """Only 2 quarters of history -- deliberately insufficient for
    compute_sue (needs > sue_lag_quarters = 4 just for one seasonal diff)."""
    adsh = "0000000003-23-000004"
    sub = [dict(adsh=adsh, cik=3, form="10-Q", period=20230930, fy=2023, fp="Q3", filed=20231103)]
    quarters_ends = pd.date_range("2023-03-31", periods=2, freq="QE")
    num = [
        dict(adsh=adsh, tag="EarningsPerShareDiluted", version="us-gaap/2023", ddate=int(d.strftime("%Y%m%d")), qtrs=1, uom="USD/shares", value=0.10 + 0.01 * i)
        for i, d in enumerate(quarters_ends)
    ]
    return sub, num


@pytest.fixture
def patched_probe(monkeypatch, tmp_path):
    cik1_sub, cik1_num = _cik1_sub_num_rows()
    cik3_sub, cik3_num = _cik3_sub_num_rows()
    sub_rows = cik1_sub + cik3_sub
    num_rows = cik1_num + cik3_num

    def fake_fetch_submission(cik, session=None):
        if cik == "0000000002":
            raise ConnectionError("simulated: SEC submissions endpoint unreachable for this CIK")
        names = {"0000000001": "Acme Corp", "0000000003": "Gamma Micro Inc"}
        return {"cik": cik.zfill(10), "name": names[cik], "sic_code": "3571", "exchanges": ["Nasdaq"], "former_names": []}

    def fake_fetch_quarter(quarter, session=None):
        assert quarter == "2023q3"
        return pd.DataFrame(sub_rows), pd.DataFrame(num_rows)

    def fake_fetch_item_202_filings(cik, session=None):
        if cik == "0000000002":
            raise ConnectionError("simulated: SEC submissions endpoint unreachable for this CIK")
        if cik == "0000000001":
            raw = {
                "cik": 1,
                "filings": {
                    "recent": {
                        "form": ["10-Q", "8-K"],
                        "accessionNumber": ["0000000001-23-000009", "0000000001-23-000008"],
                        "filingDate": ["2023-11-02", "2023-10-30"],
                        "acceptanceDateTime": ["2023-11-02T16:12:00.000Z", "2023-10-30T16:05:00.000Z"],
                        "items": ["", "2.02,9.01"],
                    }
                },
            }
            return parse_submission_filings_for_item_202(raw)
        # CIK 3: no qualifying 8-K on record
        raw = {"cik": 3, "filings": {"recent": {"form": [], "accessionNumber": [], "filingDate": [], "acceptanceDateTime": [], "items": []}}}
        return parse_submission_filings_for_item_202(raw)

    monkeypatch.setattr(h11_data_probe, "fetch_submission", fake_fetch_submission)
    monkeypatch.setattr(h11_data_probe, "fetch_quarter", fake_fetch_quarter)
    monkeypatch.setattr(h11_data_probe, "fetch_item_202_filings", fake_fetch_item_202_filings)
    monkeypatch.setattr(h11_data_probe, "OUT_DIR", tmp_path / "h11_probe")
    return tmp_path / "h11_probe"


class TestProbeEndToEnd:
    def test_probe_runs_without_raising(self, patched_probe):
        h11_data_probe.probe(ciks=["0000000001", "0000000002", "0000000003"], quarters=["2023q3"])

    def test_expected_outputs_are_written(self, patched_probe):
        h11_data_probe.probe(ciks=["0000000001", "0000000002", "0000000003"], quarters=["2023q3"])
        out_dir = patched_probe
        assert (out_dir / "identifiers.csv").exists()
        assert (out_dir / "events.csv").exists()
        assert (out_dir / "report.md").exists()
        assert (out_dir / "report.json").exists()
        assert (out_dir / "diagnostics" / "stage0_log.json").exists()
        assert (out_dir / "diagnostics" / "stage3_log.json").exists()

    def test_cik1_produces_exactly_one_event_via_8k_source(self, patched_probe):
        h11_data_probe.probe(ciks=["0000000001", "0000000002", "0000000003"], quarters=["2023q3"])
        events = pd.read_csv(patched_probe / "events.csv")
        assert len(events) == 1
        assert events.iloc[0]["entity_id"] == 1  # pandas read_csv infers int for a zero-padded-looking numeric string... see note below
        assert events.iloc[0]["event_source"] == "8k_item202"

    def test_report_counts_match_the_three_distinct_outcomes(self, patched_probe):
        h11_data_probe.probe(ciks=["0000000001", "0000000002", "0000000003"], quarters=["2023q3"])
        report = json.loads((patched_probe / "report.json").read_text())

        assert report["ciks_attempted"] == 3
        assert report["ciks_ticker_resolved"] == 2  # CIK 1 and 3; CIK 2's fetch_submission raised
        assert report["cik_ticker_resolution_failures"] == 1
        assert report["events_identified"] == 1

        reasons = {row["reason"]: row["count"] for row in report["attrition"]}
        assert reasons.get("event_built") == 1  # CIK 1
        assert reasons.get("no_eps_records_for_cik") == 1  # CIK 2 -- no fixture data supplied at all
        assert reasons.get("insufficient_history_for_any_seasonal_diff") == 1  # CIK 3 -- only 2 quarters on file

    def test_standard_tag_rate_is_100_pct_for_this_fixture(self, patched_probe):
        # every EPS-like fact in this fixture uses the standard tag --
        # confirms the tag-rate reporting wires through the full script,
        # not just the unit-tested extract_eps_records/custom_tag_fallback_rate
        # functions in isolation
        h11_data_probe.probe(ciks=["0000000001", "0000000002", "0000000003"], quarters=["2023q3"])
        report = json.loads((patched_probe / "report.json").read_text())
        assert report["standard_tag_rate"] == pytest.approx(1.0)
        assert report["custom_tag_fallback_rate"] == pytest.approx(0.0)
