"""
wikipedia_pageviews_connector.py -- pulls free, official, precisely
timestamped Wikipedia pageview data for hypothesis H13 / Part-4 idea #13
(attention proxies).

RUN THIS LOCALLY. No API key required -- the Wikimedia REST API is fully
open. Rate limit: be a good citizen, ~100 req/sec ceiling, add a real
User-Agent identifying your project (Wikimedia requires this).

Usage:
    python wikipedia_pageviews_connector.py --pages "Apple_Inc." "Tesla,_Inc." \
        --start 20180101 --end 20241231 --out wiki_features.csv

Every row is stamped with the exact UTC date the pageview count covers --
Wikipedia pageview data has no revision/restatement issue (unlike Google
Trends, which silently rescales retroactively), so known_at == period_end
here is genuinely safe, not a simplification.
"""
import argparse
import time

import pandas as pd
import requests

BASE = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        "en.wikipedia/all-access/all-agents/{page}/daily/{start}/{end}")
HEADERS = {"User-Agent": "independent-quant-research/1.0 (research use)"}


def fetch_page(page: str, start: str, end: str) -> pd.DataFrame:
    url = BASE.format(page=page, start=start, end=end)
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    items = r.json()["items"]
    df = pd.DataFrame(items)
    df["date"] = pd.to_datetime(df["timestamp"], format="%Y%m%d%H")
    df["entity_id"] = page
    df["feature_name"] = "wiki_pageviews"
    df["known_at"] = df["date"] + pd.Timedelta(days=1)  # published next day, be conservative
    df["period_end"] = df["date"]
    df = df.rename(columns={"views": "value"})
    return df[["entity_id", "feature_name", "known_at", "value", "period_end"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", nargs="+", required=True, help="exact Wikipedia article titles, underscores for spaces")
    ap.add_argument("--start", required=True, help="YYYYMMDD")
    ap.add_argument("--end", required=True, help="YYYYMMDD")
    ap.add_argument("--out", default="wiki_features.csv")
    args = ap.parse_args()

    frames = []
    for p in args.pages:
        frames.append(fetch_page(p, args.start, args.end))
        time.sleep(0.2)  # be polite to the free API
    out = pd.concat(frames, ignore_index=True)
    out.to_csv(args.out, index=False)
    print(f"wrote {len(out)} rows to {args.out}")


if __name__ == "__main__":
    main()
