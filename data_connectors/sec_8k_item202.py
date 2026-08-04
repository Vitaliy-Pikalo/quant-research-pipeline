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

HONESTY FLAG, RESOLVED: the exact JSON shape parsed here (submissions
API's filings.recent parallel-array structure, including the `items` and
`acceptanceDateTime` fields) was implemented against SEC's documented API
pattern before ever being verified against a live response (this sandbox
cannot reach data.sec.gov). It has since been run live -- see the H11 Phase
0 probe reports -- and the shape assumption held. What did NOT hold:
`acceptance_datetime` was parsed as whatever timezone SEC sends (UTC, via
the "Z" suffix on `acceptanceDateTime`) and left there, never converted to
US/Eastern. H11_PREREGISTRATION.md section 6 and event_study.schemas.Event
both require `known_at` to be interpretable in US/Eastern for the 4pm-ET
same-day-vs-next-day entry rule. A real probe run surfaced this directly:
an event built from an 8-K's acceptance_datetime carried a `+00:00` (UTC)
offset while the 10-Q-fallback path's `known_at` correctly carried `-04:00`
(Eastern) -- the exact kind of point-in-time-precision bug this project's
rigor stack exists to catch. Fixed below by converting to US/Eastern at
parse time, the same way h11_data_probe.py's 10-Q fallback path already
did; see tests/test_sec_connectors.py's
TestAcceptanceDatetimeTimezoneConversion for the regression coverage
(UTC input, Eastern conversion correctness across a DST boundary, and the
4pm-ET cutoff behavior via determine_entry_date).
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

    acceptance_datetime is returned tz-aware in US/Eastern, not the UTC SEC
    sends it in -- H11_PREREGISTRATION.md section 6's 4pm-ET entry rule and
    event_study.schemas.Event both require this. `utc=True` forces a
    tz-aware UTC interpretation even if a given record's timestamp string
    happens to lack an explicit offset (defensive; SEC's own
    acceptanceDateTime values are documented to always include one), then
    `.tz_convert` maps to Eastern -- the identical pattern
    h11_data_probe.py's 10-Q-fallback path already used for `filed`, now
    applied here too so both known_at sources are consistent.
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
    result["acceptance_datetime"] = pd.to_datetime(result["acceptance_datetime"], utc=True).dt.tz_convert("US/Eastern")
    return result[["cik", "accession_number", "form", "items", "filing_date", "acceptance_datetime"]].reset_index(
        drop=True
    )


PERIODIC_FORMS_DEFAULT = ("10-K", "10-Q", "10-KT", "10-QT")


def parse_submission_filings_for_periodic(
    raw_submission: dict, forms: tuple[str, ...] = PERIODIC_FORMS_DEFAULT
) -> pd.DataFrame:
    """
    Same parallel-array pivot as parse_submission_filings_for_item_202, but
    filtered to PERIODIC reports (10-K/10-Q and their transition variants)
    rather than 8-K Item 2.02.

    WHY: the SEC Financial Statement Data Sets' sub.txt gives a periodic
    filing's `filed` as a DATE ONLY (YYYYMMDD), with no time. Reading a
    date-only field as an instant requires a convention, and the convention
    previously in use (parse as UTC midnight, convert to Eastern) placed the
    filing at ~20:00 ET on the PREVIOUS calendar day -- see the defect list
    in hypotheses/h11_pead/known_at_resolver.py. The submissions API carries
    the real `acceptanceDateTime` for periodic filings exactly as it does
    for 8-Ks, so where a filing appears here the ambiguity disappears
    entirely rather than being resolved by picking a convention. That makes
    preferring this source a plain engineering improvement, not a
    research-definition change.

    LIMITATION, stated rather than worked around: `filings.recent` holds
    only the most recent block of filings (documented as roughly the last
    1000, or one year, whichever is larger); older filings live in the
    separate `filings.files` archives, which this function does NOT fetch.
    For a 2015-2025 build, most older periodic filings will therefore NOT be
    found here and the caller falls back to sub.txt's date-only value. The
    caller records which path each row took so the real prevalence of the
    fallback is measured, not assumed.

    Returns columns: cik, accession_number, form, report_date, filing_date,
    acceptance_datetime (tz-aware US/Eastern, same conversion and same
    reasoning as the Item 2.02 path -- both known_at sources must be
    expressed in the same timezone or the section 6 4pm-ET rule is applied
    to inconsistent inputs).
    """
    cik = str(raw_submission["cik"]).zfill(10)
    recent = raw_submission["filings"]["recent"]

    n = len(recent["form"])
    df = pd.DataFrame(
        {
            "form": recent["form"],
            "accession_number": recent["accessionNumber"],
            "filing_date": recent["filingDate"],
            "report_date": recent.get("reportDate", [None] * n),
            "acceptance_datetime": recent.get("acceptanceDateTime", [None] * n),
        }
    )
    df["cik"] = cik

    result = df[df["form"].isin(list(forms))].copy()
    result["filing_date"] = pd.to_datetime(result["filing_date"], errors="coerce")
    result["report_date"] = pd.to_datetime(result["report_date"], errors="coerce")
    result["acceptance_datetime"] = pd.to_datetime(result["acceptance_datetime"], utc=True, errors="coerce").dt.tz_convert(
        "US/Eastern"
    )
    return result[["cik", "accession_number", "form", "report_date", "filing_date", "acceptance_datetime"]].reset_index(
        drop=True
    )


def fetch_raw_submission(
    cik: str, session: requests.Session | None = None, telemetry: RequestTelemetryCollector | None = None
) -> dict:  # pragma: no cover -- network
    """
    One request, raw JSON, so a caller needing more than one view of the
    same submissions payload (identifiers, Item 2.02 8-Ks, periodic
    acceptance timestamps) can parse it three ways off a single fetch
    instead of hitting the identical URL three times. Directly addresses the
    duplication fetch_item_202_filings' own docstring flagged from telemetry.
    Endpoint label stays "sec_submissions" so the saving is visible in the
    telemetry summary as a drop in request count against the same endpoint.
    """
    session = session or requests.Session()
    url = SUBMISSIONS_URL_TMPL.format(cik=int(cik))
    resp = instrumented_get(
        session, url, headers={"User-Agent": SEC_USER_AGENT}, timeout=30, endpoint_label="sec_submissions", telemetry=telemetry
    )
    return resp.json()


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
