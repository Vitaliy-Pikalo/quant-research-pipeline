"""
data_connectors/sec_company_tickers.py -- SEC's official CIK<->ticker and
submissions metadata, free, no key.

Per H11_data_availability_review.md section 5, this is the input to the
highest-risk mapping in this project's H11 design. This connector only
supplies the OFFICIAL CIK<->current-ticker mapping and per-CIK submission
metadata (SIC code, former names, exchanges) -- it deliberately does NOT
attempt point-in-time ticker history on its own, since SEC's own files only
give the *current* ticker per CIK. Point-in-time resolution
(event_study.identifiers.PointInTimeTickerHistory) is built from a
DIFFERENT source (ticker-change events over time) and is out of scope for
this connector; conflating "SEC says this is CIK X's ticker today" with
"this was CIK X's ticker on every past date" is exactly the kind of error
category this project has been burned by before (H10's recycled BRKL).

fetch_* functions require network access to www.sec.gov / data.sec.gov,
which this project's Claude sandbox cannot reach (confirmed by direct test
during the H11 data availability review -- only pypi.org and github.com
resolve). They are written correctly but UNTESTED against live data here;
run locally per this project's standing workflow (Claude writes the script,
the user runs it, Claude reads the output files). parse_* functions contain
all the logic that can go wrong and are fully unit-tested against fixture
data matching SEC's documented response shape.
"""
from __future__ import annotations

import pandas as pd
import requests

SEC_USER_AGENT = "quant-research-pipeline research@example.com"  # replace with a real contact before running live
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL_TMPL = "https://data.sec.gov/submissions/CIK{cik:0>10}.json"


def parse_company_tickers(raw: dict) -> pd.DataFrame:
    """
    raw : the parsed JSON from company_tickers.json, shaped as
        {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
        (SEC serves this as an object keyed by string indices, not a list.)
    """
    rows = list(raw.values())
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["cik", "ticker", "company_name"])
    df = df.rename(columns={"cik_str": "cik", "title": "company_name"})
    df["cik"] = df["cik"].astype(str).str.zfill(10)
    return df[["cik", "ticker", "company_name"]]


def parse_submission(raw: dict) -> dict:
    """
    raw : the parsed JSON from data.sec.gov/submissions/CIK##########.json.
    Returns a flat dict: cik, name, sic_code, exchanges (list),
    former_names (list of {name, from, to}).
    """
    return {
        "cik": str(raw["cik"]).zfill(10),
        "name": raw.get("name"),
        "sic_code": raw.get("sic"),
        "exchanges": raw.get("exchanges", []),
        "former_names": [
            {"name": fn.get("name"), "from": fn.get("from"), "to": fn.get("to")}
            for fn in raw.get("formerNames", [])
        ],
    }


def fetch_company_tickers(session: requests.Session | None = None) -> pd.DataFrame:  # pragma: no cover -- network
    session = session or requests.Session()
    resp = session.get(COMPANY_TICKERS_URL, headers={"User-Agent": SEC_USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return parse_company_tickers(resp.json())


def fetch_submission(cik: str, session: requests.Session | None = None) -> dict:  # pragma: no cover -- network
    session = session or requests.Session()
    url = SUBMISSIONS_URL_TMPL.format(cik=int(cik))
    resp = session.get(url, headers={"User-Agent": SEC_USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return parse_submission(resp.json())
