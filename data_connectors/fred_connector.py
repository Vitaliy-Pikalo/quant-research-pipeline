"""
fred_connector.py -- pulls free FRED series for hypothesis H9 (FX carry /
UIP violation) and similar macro-driven signals.

RUN THIS LOCALLY, NOT IN A NETWORK-RESTRICTED SANDBOX. Get a free API key
at https://fred.stlouisfed.org/docs/api/api_key.html (instant, no cost).

Usage:
    export FRED_API_KEY=your_key_here
    python fred_connector.py --series DGS3MO DEXUSEU DEXJPUS --start 2010-01-01

Writes each series into a PITFeatureStore-compatible CSV (entity_id,
feature_name, known_at, value). For FRED, known_at = release date, which
FRED's own API exposes via the 'realtime_start' field on ALFRED (the
real-time/vintage version of the API) -- use ALFRED, not the standard FRED
endpoint, if you need genuinely point-in-time-correct vintages (the
standard endpoint returns the LATEST revised value under each historical
date, which is itself a look-ahead-bias trap for revised series like GDP;
less of an issue for interest-rate/FX series, which are rarely revised).
"""
import argparse
import os
import sys

import pandas as pd
import requests

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


def fetch_series(series_id: str, api_key: str, start: str) -> pd.DataFrame:
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start,
    }
    r = requests.get(FRED_BASE, params=params, timeout=30)
    r.raise_for_status()
    obs = r.json()["observations"]
    df = pd.DataFrame(obs)
    df = df[df["value"] != "."]  # FRED uses "." for missing
    df["value"] = df["value"].astype(float)
    df["date"] = pd.to_datetime(df["date"])
    df["entity_id"] = series_id
    df["feature_name"] = series_id
    df["known_at"] = df["date"]  # see docstring: use ALFRED for true vintages
    df["period_end"] = df["date"]
    return df[["entity_id", "feature_name", "known_at", "value", "period_end"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", nargs="+", required=True,
                     help="e.g. DGS3MO (3-month T-bill), DEXUSEU (USD/EUR), DEXJPUS (JPY/USD)")
    ap.add_argument("--start", default="2000-01-01")
    ap.add_argument("--out", default="fred_features.csv")
    args = ap.parse_args()

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        sys.exit("Set FRED_API_KEY env var. Get a free key: "
                 "https://fred.stlouisfed.org/docs/api/api_key.html")

    frames = [fetch_series(s, api_key, args.start) for s in args.series]
    out = pd.concat(frames, ignore_index=True)
    out.to_csv(args.out, index=False)
    print(f"wrote {len(out)} rows to {args.out}")
    print("Load into PITFeatureStore with: store.write_batch(pd.read_csv(args.out, parse_dates=['known_at','period_end']))")


if __name__ == "__main__":
    main()
