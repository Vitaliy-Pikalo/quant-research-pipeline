"""
edgar_13f_connector.py -- pulls free SEC EDGAR 13F structured data for
hypothesis H8 (13F institutional herding / copycat decay).

RUN THIS LOCALLY. No API key required, but SEC requires a descriptive
User-Agent with contact info (they will rate-limit/block generic agents).

Usage:
    python edgar_13f_connector.py --cik 0001067983 --out berkshire_13f.csv
    (0001067983 is Berkshire Hathaway's CIK; look up others at
    https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany)

This pulls the *filing index* for a manager's 13F-HR filings (quarterly
holdings snapshots) and extracts filing timestamps -- the critical
PIT field (known_at). Parsing the actual holdings XML (form13fInfoTable)
per filing is a further step (SEC publishes an XML schema per filing);
this script gives you the filing-level scaffold plus the exact accession
numbers you need to pull each holdings table.
"""
import argparse
import time

import pandas as pd
import requests

HEADERS = {"User-Agent": "Independent Quant Research contact@example.com"}


def fetch_filing_index(cik: str) -> pd.DataFrame:
    cik_padded = cik.zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    recent = data["filings"]["recent"]
    df = pd.DataFrame({
        "form": recent["form"],
        "filingDate": recent["filingDate"],
        "reportDate": recent["reportDate"],
        "accessionNumber": recent["accessionNumber"],
        "primaryDocument": recent["primaryDocument"],
    })
    df = df[df["form"].isin(["13F-HR", "13F-HR/A"])].copy()
    df["entity_id"] = data.get("name", cik)
    df["known_at"] = pd.to_datetime(df["filingDate"])   # PIT-correct: actual filing timestamp
    df["period_end"] = pd.to_datetime(df["reportDate"])  # quarter the holdings describe
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cik", required=True, help="SEC CIK number, e.g. 0001067983 for Berkshire Hathaway")
    ap.add_argument("--out", default="13f_filing_index.csv")
    args = ap.parse_args()

    df = fetch_filing_index(args.cik)
    df.to_csv(args.out, index=False)
    print(f"wrote {len(df)} 13F filing records to {args.out}")
    print("Next step: for each accessionNumber, fetch the form13fInfoTable XML at")
    print("https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{primaryDocument}")
    print("to get the actual per-holding position data (ticker, shares, value).")


if __name__ == "__main__":
    main()
