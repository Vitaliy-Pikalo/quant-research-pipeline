"""
h10b_district_assign.py -- H10b step 2: derive each constituent's Federal
Reserve district from the FDIC record and publish every disagreement with
the hand-built map BEFORE any return is computed.

Required by section 4 of H10b_PREREGISTRATION.md:

    "HQ state is taken from the FDIC record, not from our hand-built map.
     District assignment for H10b is derived from the FDIC institution's
     own state, and any constituent whose FDIC-derived district disagrees
     with our hand-built assignment will be reassigned to the FDIC-derived
     one, with every such change listed in the results before any return
     is computed."

WHY NOT DERIVE THE DISTRICT FROM THE STATE
-------------------------------------------
Because state does not determine district. Illinois is split between
Chicago (7th) and St. Louis (8th); Pennsylvania between Philadelphia
(3rd) and Cleveland (4th); Missouri between St. Louis (8th) and Kansas
City (10th); New Jersey between New York (2nd) and Philadelphia (3rd);
Indiana between Chicago and St. Louis. Half this sample sits in a split
state, so a state-level rule would be guessing precisely where it matters.

FDIC stamps every institution with the Federal Reserve district of its
charter (FED / FEDNAME). That is the Fed's own assignment, resolves the
split states, and is what section 4 means by "FDIC-derived".

CAVEAT WORTH STATING: this is the district of the CHARTER, which is not
always where the franchise's economy is. U.S. Bancorp is headquartered in
Minneapolis but U.S. Bank N.A. is chartered in Cincinnati, so FDIC places
it in Cleveland. For a national bank the answer is arguably "neither",
which is exactly why H10b weights it near zero regardless of which
district it lands in.

Usage:
    python h10b_district_assign.py

Input:  h10b_fdic_resolution.csv, fed_district_bank_map.csv
Output: h10b_district_assignment.csv
"""
from __future__ import annotations

import json
import os
import sys
import time

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
for _p in (REPO, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _find(name):
    """Resolve a data file from repo/data, the script's directory, or cwd, so
    this runs both inside the repo and from a flat working directory."""
    for c in (os.path.join(REPO, "data", name), os.path.join(HERE, name), name):
        if os.path.exists(c):
            return c
    return name

API = "https://api.fdic.gov/banks"
HEADERS = {"User-Agent": "research script (district assignment)"}
CACHE = ".fdic_cache"
SLEEP = 0.6
BACKOFF = [5, 15, 30, 60]


def get(path, params):
    for i, wait in enumerate([0] + BACKOFF):
        if wait:
            time.sleep(wait)
        try:
            r = requests.get(f"{API}/{path}", params=params, headers=HEADERS, timeout=60)
        except requests.RequestException:
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            ra = r.headers.get("Retry-After")
            if ra and ra.isdigit():
                time.sleep(int(ra))
    return None


def fed_for_cert(cert):
    cp = os.path.join(CACHE, f"fed_{cert}.json")
    if os.path.exists(cp):
        with open(cp) as f:
            return json.load(f)
    # latest vintage the charter appears in carries its current district
    js = get("sod", {"filters": f"CERT:{cert}", "fields": "CERT,YEAR,FED,FEDNAME",
                     "sort_by": "YEAR", "sort_order": "DESC", "limit": 1, "format": "json"})
    if not js or not js.get("data"):
        return None
    d = js["data"][0]["data"]
    out = {"fed": d.get("FED"), "fedname": d.get("FEDNAME"), "year": d.get("YEAR")}
    os.makedirs(CACHE, exist_ok=True)
    with open(cp, "w") as f:
        json.dump(out, f)
    return out


def main():
    res = pd.read_csv(_find("h10b_fdic_resolution.csv"))
    hand = pd.read_csv(_find("fed_district_bank_map.csv"))
    hand_map = dict(zip(hand.ticker, hand.district))

    rows = []
    print("querying FDIC for each charter's Federal Reserve district...")
    for _, r in res.iterrows():
        info = fed_for_cert(int(r.cert))
        time.sleep(SLEEP)
        if not info:
            print(f"  {r.ticker:5s} LOOKUP FAILED")
            rows.append({"ticker": r.ticker, "fdic_name": r.fdic_name,
                         "hq_state": r.fdic_state, "hand_district": hand_map.get(r.ticker),
                         "fdic_district": None, "changed": None})
            continue
        rows.append({
            "ticker": r.ticker, "fdic_name": r.fdic_name, "hq_state": r.fdic_state,
            "hand_district": hand_map.get(r.ticker),
            "fdic_district": info["fedname"], "fed_number": info["fed"],
            "as_of_vintage": info["year"],
            "changed": hand_map.get(r.ticker) != info["fedname"],
        })

    df = pd.DataFrame(rows)
    df.to_csv("h10b_district_assignment.csv", index=False)

    print("\n" + "=" * 74)
    print("DISTRICT ASSIGNMENT -- FDIC vs hand-built map")
    print("=" * 74)
    print(df[["ticker", "fdic_name", "hq_state", "hand_district",
              "fdic_district", "changed"]].to_string(index=False))

    ch = df[df.changed == True]  # noqa: E712
    print(f"\nreassignments: {len(ch)} of {len(df)}")
    if len(ch):
        print(ch[["ticker", "hq_state", "hand_district", "fdic_district"]].to_string(index=False))

    print("\nresulting constituents per district (FDIC-derived):")
    cnt = df.groupby("fdic_district").size().sort_values(ascending=False)
    print(cnt.to_string())
    missing = set(hand.district.unique()) - set(df.fdic_district.dropna())
    if missing:
        print(f"\nDISTRICTS WITH NO CONSTITUENTS AFTER REASSIGNMENT: {sorted(missing)}")
        print("These cannot be ranked cross-sectionally and must be handled explicitly.")

    print("\nwrote h10b_district_assignment.csv")
    print("NO returns computed.")


if __name__ == "__main__":
    main()
