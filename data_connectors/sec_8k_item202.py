"""
data_connectors/sec_8k_item202.py -- 8-K Item 2.02 (earnings release)
accession timestamps, free, no key.

Uses the SEC submissions API's per-filing `items` field (each 8-K's
submission record lists which items it reports, e.g. "2.02,9.01") rather
than full-text search or document text-scanning -- this is the most
reliable documented source for item-level filtering, and gives
`acceptanceDateTime`, the actual EDGAR accession timestamp (to the second),
which is what H11_PREREGISTRATION.md section 6 requires as `known_at` --
NOT `filingDate`, which is calendar-date-only and would throw away exactly
the intraday precision this design's point-in-time contribution depends on.

HONESTY FLAG: the exact JSON shape parsed here (submissions API's
filings.recent parallel-array structure, including the `items` and
`acceptanceDateTime` fields) is implemented against SEC's documented API
pattern but has not been verified against a live response from this
sandbox (network to data.sec.gov is unreachable here -- confirmed during
the H11 data availability review). The parse function's first real use
against a real submissions payload (via h11_data_probe.py, run locally)
should specifically check this shape assumption before trusting any output,
per H11_IMPLEMENTATION_SPEC.md section 4 (stage 0 validation).
"""
from __future__ import annotations

import pandas as pd
import requests

from data_connectors.telemetry import RequestTelemetryCollector, instrumented_get

SEC_USER_AGENT = "Vitaliy Pikalo pikalo.vitaliy@gmail.com"  # real identifying contact per SEC's fair-access policy
SUBMISSIONS_URL_TMPL = "https://data.sec.gov/submissions/CIK{cik:0>10}.json"

ITEM_202_PATTERN = r"2\.02"


def parse_submission_filings_for_item_202(raw_submission: dict) -> pd.DataFrame:
    """
    raw_submission : parsed JSON from data.sec.gov/submissions/CIK##########.json.
    SEC represents recent filings as parallel arrays under
    filings.recent.{form, accessionNumber, filingDate, acceptanceDateTime,
    items, ...} -- one index position per filing, not a list of per-filing
    objects. This function pivots that into a normal per-row DataFrame and
    filters to 8-Ks whose `items` field contains "2.02".

    Returns columns: cik, accession_number, form, items, filing_date,
    acceptance_datetime (this last one is `known_at` for a primary-source
    H11 event, per section 4/6 of the pre-registration).
    """
    cik = str(raw_submission["cik"]).zfill(10)
    recent = raw_submission["filings"]["recent"]

    n = len(recent["form"])
    df = pd.DataFrame(
        {
            "form": recent["form"],
            "accession_number": recent["accessionNumber"],
            "filing_date": recent["filingDate"],
            "acceptance_datetime": recent.get("acceptanceDateTime", [None] * n),
            "items": recent.get("items", [""] * n),
        }
    )
    df["cik"] = cik

    is_8k = df["form"] == "8-K"
    # .astype(str) before .str.contains() is deliberate, not redundant: a
    # submission with zero recent filings (n == 0, a genuinely empty but
    # valid response -- e.g. a very new filer, or the fallback stub used
    # when a live fetch fails) produces an empty "items" column that pandas
    # infers as float64 rather than object/string, and `.str.contains()`
    # raises AttributeError on a non-string-dtype Series. Caught by
    # tests/test_h11_data_probe_e2e.py's empty-submission-fallback case,
    # not found by any fixture with at least one real filing.
    has_202 = df["items"].astype(str).fillna("").str.contains(ITEM_202_PATTERN, regex=True)
    result = df[is_8k & has_202].copy()

    result["filing_date"] = pd.to_datetime(result["filing_date"])
    result["acceptance_datetime"] = pd.to_datetime(result["acceptance_datetime"])
    return result[["cik", "accession_number", "form", "items", "filing_date", "acceptance_datetime"]].reset_index(
        drop=True
    )


def fetch_item_202_filings(
    cik: str, session: requests.Session | None = None, telemetry: RequestTelemetryCollector | None = None
) -> pd.DataFrame:  # pragma: no cover -- network
    """
    NOTE surfaced by telemetry, not changed here (out of scope for this
    instrumentation-only milestone): this hits the exact same
    data.sec.gov/submissions/CIK##########.json endpoint as
    sec_company_tickers.fetch_submission(). A probe run currently makes two
    separate requests per CIK to the identical URL -- one for identifiers,
    one for 8-K detection -- rather than fetching it once and reusing the
    payload. Endpoint label is deliberately "sec_submissions" (matching
    fetch_submission's label, not a distinct one), so this duplication is
    visible in the telemetry summary rather than hidden behind two
    differently-named endpoints that look unrelated.
    """
    session = session or requests.Session()
    url = SUBMISSIONS_URL_TMPL.format(cik=int(cik))
    resp = instrumented_get(
        session, url, headers={"User-Agent": SEC_USER_AGENT}, timeout=30, endpoint_label="sec_submissions", telemetry=telemetry
    )
    return parse_submission_filings_for_item_202(resp.json())
