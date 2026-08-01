"""
fdic_locality_pull.py -- H10b step 1: build the locality table.

Implements sections 4 and 5 of H10b_PREREGISTRATION.md and NOTHING ELSE.
No price data is touched and no return, IC, Sharpe or p-value is computed
here. The only output is a per-bank, per-year locality score, published
for review while the answer to the hypothesis is still unknown.

LOCALITY MEASURE (pre-registered)
---------------------------------
    L(i, Y) = deposits in branches in bank i's HQ state
              --------------------------------------------
              bank i's total domestic deposits

FDIC Summary of Deposits, https://api.fdic.gov/banks/sod, free, no key.
Branch deposits are DEPSUMBR, branch state STALPBR. A single-state
community bank scores near 1.0; a national franchise scores low.

POINT-IN-TIME (pre-registered)
------------------------------
SOD is measured 30 June, published end of September. A Beige Book release
on date t uses vintage Y where Y is the largest year with t >= 1 Oct of Y.
Applied downstream; this script produces all vintages 2009-2025.

--------------------------------------------------------------------
THREE FAILURES THIS SCRIPT IS BUILT AROUND, ALL FOUND THE HARD WAY
--------------------------------------------------------------------
1. AMBIGUOUS BANK NAMES. "United Bank" matched United Fidelity Bank
   (Indiana, holding company PEDCOR FINANCIAL) ahead of United
   Bankshares' West Virginia charters. Names are not unique across
   states, and relevance ranking alone picked the wrong institution.
   Fix: search within the expected state first, and verify the match.

2. TODAY'S STRUCTURE IS NOT HISTORY'S. Zions and Flagstar both return a
   blank holding company from the institutions endpoint, which would
   collapse them to a single charter. Zions ran Amegy (TX), California
   Bank & Trust and Nevada State Bank as separate charters until it
   consolidated around 2018. Aggregating only the Utah charter would
   drop those branches and make Zions look far more Utah-local in the
   early sample than it was -- inflating the exact variable this
   exercise turns on. Fix: read the holding company per VINTAGE YEAR
   from the SOD record, not once from today's institution record.

3. RATE LIMITING THAT LOOKED LIKE MISSING DATA. Per-year querying
   triggered HTTP 429s; retries were exhausted and the script moved on,
   producing "11/17 vintages" for one bank and 15/17 for another. Those
   gaps would have entered the locality table as absent years and
   silently changed the weights. Fixes: (a) YEAR:[a TO b] range queries,
   cutting ~34 requests per bank to ~3, (b) real exponential backoff
   that honours Retry-After, (c) an on-disk cache so a rerun resumes
   rather than restarting, and (d) a hard failure at the end if any bank
   is missing any vintage. Silence is not success.

Usage:
    pip install requests pandas
    python fdic_locality_pull.py

Output:
    h10b_fdic_resolution.csv   ticker -> FDIC institution, for review
    h10b_locality.csv          ticker x year -> locality score
    .fdic_cache/               raw pulls, so reruns are cheap
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from difflib import SequenceMatcher

import pandas as pd
import requests

API = "https://api.fdic.gov/banks"
HEADERS = {"User-Agent": "research script (locality study)"}
Y0, Y1 = 2009, 2025
YEARS = list(range(Y0, Y1 + 1))
CACHE = ".fdic_cache"
SLEEP = 0.8
BACKOFF = [5, 15, 30, 60, 90]
MIN_NAME_SIM = 0.55   # below this, the name match is not trustworthy -- stop

BANKS = {
    "BHLB": ("Berkshire Bank", "MA"),
    "INDB": ("Rockland Trust Company", "MA"),
    "MTB":  ("Manufacturers and Traders Trust Company", "NY"),
    "VLY":  ("Valley National Bank", "NJ"),
    # Resolve to the HISTORICAL charter, not today's surviving one. Searching
    # "Flagstar Bank" returns CERT 32541, which was a MICHIGAN thrift until
    # NYCB acquired Flagstar in 2022 and kept Flagstar's charter as the
    # survivor. That charter's 2009-2021 deposits are Michigan's, and
    # attaching them to a New York district constituent produced a locality
    # of 0.000 in 2009 -- zero deposits in its own HQ state. New York
    # Community Bank is CERT 16022 (ended 12/2022); its holding company RSSD
    # 2132932 persists through the rename and still covers the Flagstar
    # charter in 2024, so the franchise is tracked continuously.
    "NYCB": ("New York Community Bank", "NY"),
    "FULT": ("Fulton Bank", "PA"),
    "CUBI": ("Customers Bank", "PA"),
    # WSFS is the acronym; the chartered name is spelled out. Using the ticker
    # short-name scored 0.25 on similarity and tripped the guard, correctly --
    # the guard was right that the strings disagree, even though the match was
    # right. Fixed by searching the real name rather than relaxing the gate.
    "WSFS": ("Wilmington Savings Fund Society", "DE"),
    "KEY":  ("KeyBank National Association", "OH"),
    "HBAN": ("The Huntington National Bank", "OH"),
    "FITB": ("Fifth Third Bank", "OH"),
    "TFC":  ("Truist Bank", "NC"),
    "UBSI": ("United Bank", "WV"),
    "AUB":  ("Atlantic Union Bank", "VA"),
    "RF":   ("Regions Bank", "AL"),
    "ABCB": ("Ameris Bank", "GA"),
    "NTRS": ("The Northern Trust Company", "IL"),
    "WTFC": ("Wintrust Bank", "IL"),
    "ONB":  ("Old National Bank", "IN"),
    "SFNC": ("Simmons Bank", "AR"),
    "FMBH": ("First Mid Bank & Trust", "IL"),
    "MSBI": ("Midland States Bank", "IL"),
    "USB":  ("U.S. Bank National Association", "OH"),   # charter is Cincinnati
    "ALRS": ("Alerus Financial", "ND"),
    "GBCI": ("Glacier Bank", "MT"),
    "CBSH": ("Commerce Bank", "MO"),
    "UMBF": ("UMB Bank", "MO"),
    "BOKF": ("BOKF, National Association", "OK"),
    "CFR":  ("Frost Bank", "TX"),
    "PB":   ("Prosperity Bank", "TX"),
    "WAL":  ("Western Alliance Bank", "AZ"),
    "EWBC": ("East West Bank", "CA"),
    "ZION": ("Zions Bancorporation", "UT"),
}


def _cache_path(key):
    os.makedirs(CACHE, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in key)
    return os.path.join(CACHE, safe + ".json")


def get(path, params):
    """GET with real backoff. Returns None only after exhausting retries."""
    for i, wait in enumerate([0] + BACKOFF):
        if wait:
            time.sleep(wait)
        try:
            r = requests.get(f"{API}/{path}", params=params, headers=HEADERS, timeout=60)
        except requests.RequestException as e:
            print(f"      {type(e).__name__}, retry {i+1}/{len(BACKOFF)}")
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            ra = r.headers.get("Retry-After")
            if ra and ra.isdigit():
                print(f"      429, honouring Retry-After={ra}s")
                time.sleep(int(ra))
            else:
                print(f"      429 rate limited, backing off {BACKOFF[min(i, len(BACKOFF)-1)]}s")
            continue
        print(f"      HTTP {r.status_code}, retry {i+1}/{len(BACKOFF)}")
    return None


def fetch_all(filters, fields, cache_key):
    """Paginate a SOD query fully. Cached to disk; a rerun costs nothing."""
    cp = _cache_path(cache_key)
    if os.path.exists(cp):
        with open(cp) as f:
            return json.load(f)
    rows, offset = [], 0
    while True:
        js = get("sod", {"filters": filters, "fields": fields,
                         "limit": 10000, "offset": offset, "format": "json"})
        if js is None:
            return None                      # hard failure, do NOT cache
        batch = [d["data"] for d in js.get("data", [])]
        rows.extend(batch)
        total = js.get("meta", {}).get("total", 0)
        offset += len(batch)
        if not batch or offset >= total:
            break
        time.sleep(SLEEP)
    with open(cp, "w") as f:
        json.dump(rows, f)
    return rows


def resolve(ticker, name, expect_state):
    fields = "CERT,NAME,STALP,CITY,ASSET,ACTIVE,RSSDHCR,NAMEHCR"
    js = get("institutions", {"search": f'NAME:"{name}"', "filters": f"STALP:{expect_state}",
                              "fields": fields, "limit": 20, "format": "json"})
    if not js or not js.get("data"):
        js = get("institutions", {"search": f'NAME:"{name}"',
                                  "fields": fields, "limit": 20, "format": "json"})
    if not js or not js.get("data"):
        return None
    cands = [d["data"] for d in js["data"]]
    in_state = [c for c in cands if c.get("STALP") == expect_state]
    pool = in_state or cands
    # Take the BEST NAME MATCH, not the biggest bank. Picking max assets among
    # in-state candidates resolved "Truist Bank" to Bank of America: both are
    # headquartered in North Carolina and BofA is ~5x larger, so size beat the
    # institution that is literally named Truist. Size is not evidence of
    # identity. The API returns results in relevance order; combine that with
    # an explicit string-similarity score and refuse weak matches.
    def _norm(s):
        s = (s or "").lower()
        for junk in (", national association", " national association", ", n.a.",
                     " n.a.", ", fsb", " fsb", ", inc.", " inc.", "the "):
            s = s.replace(junk, " ")
        return " ".join(s.split())

    target = _norm(name)
    scored = [(SequenceMatcher(None, target, _norm(c["NAME"])).ratio(), i, c)
              for i, c in enumerate(pool)]
    # highest similarity wins; original API relevance order breaks ties
    best_sim, _, best = max(scored, key=lambda t: (t[0], -t[1]))
    best = dict(best)
    best["_state_matched"] = bool(in_state)
    best["_name_similarity"] = round(best_sim, 3)
    best["_n_candidates"] = len(cands)
    best["_runners_up"] = "; ".join(
        f"{c['NAME']}({c.get('STALP')})" for c in cands[:4] if c["CERT"] != best["CERT"])
    return best


def pull_bank(ticker, cert, hq_state, seed_hc=""):
    """All branch-year rows for this franchise, following its holding company
    structure as it actually was in each vintage year."""
    fields = "YEAR,STALPBR,DEPSUMBR,CERT,RSSDHCR"
    base = fetch_all(f"CERT:{cert} AND YEAR:[{Y0} TO {Y1}]", fields, f"cert_{cert}")
    if base is None:
        return None
    df = pd.DataFrame(base)
    if df.empty:
        return df

    def _hc(v):
        try:
            v = int(v)
        except (TypeError, ValueError):
            return ""
        return "" if v == 0 else str(v)

    df["hc"] = df["RSSDHCR"].map(_hc)

    # Two DIFFERENT situations that must not be conflated:
    #   (a) the charter reported NO holding company that year -> blank is the
    #       correct answer, aggregate by CERT alone. Zions dissolved its
    #       holding company into the bank in 2018, so 2019+ are genuinely
    #       blank.
    #   (b) the charter does not appear that year at all -> the franchise
    #       continues under another charter and the holding company must be
    #       carried in. United Bankshares folded its WV charter into the VA
    #       one, so CERT 6784 vanishes after 2017.
    # Treating (a) as (b) overwrote real blanks with a stale holding company
    # that had no rows in those years, silently deleting BHLB 2009-2014,
    # NYCB 2009-2015, WSFS 2009-2015, CUBI 2009-2011 and ZION 2019-2025.
    hc_by_year = {}
    for y, g in df.groupby("YEAR"):
        vals = [v for v in g["hc"] if v]
        hc_by_year[int(y)] = pd.Series(vals).mode().iat[0] if vals else ""

    seed = _hc(seed_hc) if seed_hc else ""
    for y in range(Y0, Y1 + 1):
        if y in hc_by_year:           # case (a): leave blanks alone
            continue
        prior = [k for k, v in hc_by_year.items() if k < y and v]
        later = [k for k, v in hc_by_year.items() if k > y and v]
        if prior:
            hc_by_year[y] = hc_by_year[max(prior)]
        elif later:
            hc_by_year[y] = hc_by_year[min(later)]
        else:
            hc_by_year[y] = seed

    frames = [df]
    # Blank is a valid VALUE in hc_by_year (it means "no holding company that
    # year, aggregate by charter"), but it is not a thing you can query for:
    # RSSDHCR:"" is a malformed filter and the API answers 400.
    for hc in sorted({v for v in hc_by_year.values() if v}):
        extra = fetch_all(f'RSSDHCR:"{hc}" AND YEAR:[{Y0} TO {Y1}]', fields, f"hc_{hc}")
        if extra is None:
            return None
        if extra:
            frames.append(pd.DataFrame(extra))
        time.sleep(SLEEP)

    allrows = pd.concat(frames, ignore_index=True)
    allrows["hc"] = allrows["RSSDHCR"].map(_hc)

    # For each year keep the widest correct footprint: every charter under
    # that year's holding company, or just this charter if there was none.
    keep = []
    for y, g in allrows.groupby("YEAR"):
        hc = hc_by_year.get(int(y), "")
        sel = g[g.hc == hc] if hc else g[g.CERT == cert]
        # belt and braces: if the carried-in holding company turns out to have
        # no rows that year, fall back to the charter rather than emit nothing
        if len(sel) == 0:
            sel = g[g.CERT == cert]
        if len(sel):
            keep.append(sel)
    if not keep:
        return pd.DataFrame()
    out = pd.concat(keep, ignore_index=True).drop_duplicates()
    out["DEPSUMBR"] = pd.to_numeric(out["DEPSUMBR"], errors="coerce").fillna(0)
    return out


def main():
    print("=" * 74)
    print("H10b STEP 1 -- FDIC locality table. NO RETURNS ARE COMPUTED HERE.")
    print("=" * 74)

    # Key the resolution cache on the CONTENT of BANKS plus the matching rule,
    # so editing a search term automatically invalidates it. A manually bumped
    # version string had already gone stale once: the cache was written before
    # the review check ran, so a corrected search term was silently ignored on
    # the next run and the bad match persisted.
    sig = hashlib.md5(
        (json.dumps(BANKS, sort_keys=True) + f"|simrule|{MIN_NAME_SIM}").encode()
    ).hexdigest()[:10]
    rcache = _cache_path(f"resolution_{sig}")
    if os.path.exists(rcache):
        rdf = pd.read_json(rcache)
        print("\nusing cached resolution")
    else:
        res = []
        print("\nresolving tickers to FDIC institutions...")
        for t, (name, st) in BANKS.items():
            r = resolve(t, name, st)
            time.sleep(SLEEP)
            if r is None:
                print(f"  {t:5s} NOT FOUND ({name})")
                res.append({"ticker": t, "search_name": name, "expected_state": st,
                            "status": "NOT_FOUND", "state_matched": False})
                continue
            flag = "" if r["_state_matched"] else "  <-- STATE MISMATCH"
            if r["_name_similarity"] < MIN_NAME_SIM:
                flag += f"  <-- WEAK NAME MATCH {r['_name_similarity']}"
            print(f"  {t:5s} -> {r['NAME'][:40]:40s} {r['STALP']} cert={r['CERT']:<6}"
                  f" sim={r['_name_similarity']:.2f} hc={str(r.get('NAMEHCR',''))[:18]:18s}{flag}")
            res.append({
                "ticker": t, "search_name": name, "expected_state": st,
                "fdic_name": r["NAME"], "fdic_state": r["STALP"], "fdic_city": r["CITY"],
                "cert": r["CERT"], "rssdhcr": str(r.get("RSSDHCR", "") or ""),
                "namehcr": r.get("NAMEHCR", ""), "asset_k": r.get("ASSET"),
                "active": r.get("ACTIVE"), "state_matched": r["_state_matched"],
                "name_similarity": r["_name_similarity"],
                "n_candidates": r["_n_candidates"], "runners_up": r["_runners_up"],
                "status": "ok",
            })
        rdf = pd.DataFrame(res)
        rdf.to_json(rcache)

    rdf["state_matched"] = rdf["state_matched"].map(lambda v: v is True or v == 1)
    if "name_similarity" not in rdf.columns:
        rdf["name_similarity"] = 0.0
    rdf["name_similarity"] = pd.to_numeric(rdf["name_similarity"], errors="coerce").fillna(0.0)
    rdf.to_csv("h10b_fdic_resolution.csv", index=False)
    bad = rdf[(rdf.status != "ok") | (~rdf["state_matched"])
              | (rdf["name_similarity"] < MIN_NAME_SIM)]
    print(f"\nresolved {int((rdf.status == 'ok').sum())}/{len(BANKS)}; {len(bad)} need review")
    if len(bad):
        cols = [c for c in ["ticker", "search_name", "expected_state", "fdic_name",
                            "fdic_state", "name_similarity", "runners_up"] if c in bad.columns]
        print(bad[cols].to_string(index=False))
        sys.exit("STOPPING: resolve these before pulling deposits.")

    print("\npulling Summary of Deposits (range queries + on-disk cache)...")
    out, failed = [], []
    for _, r in rdf.iterrows():
        d = pull_bank(r.ticker, int(r.cert), r.fdic_state, str(r.get("rssdhcr", "") or ""))
        if d is None or len(d) == 0:
            print(f"  {r.ticker:5s} PULL FAILED")
            failed.append(r.ticker)
            continue
        got = []
        for y, g in d.groupby("YEAR"):
            tot = g["DEPSUMBR"].sum()
            if tot <= 0:
                continue
            by_state = g.groupby("STALPBR")["DEPSUMBR"].sum()
            hq = float(by_state.get(r.fdic_state, 0.0))
            out.append({
                "ticker": r.ticker, "year": int(y), "hq_state": r.fdic_state,
                "total_deposits_k": float(tot), "hq_state_deposits_k": hq,
                "locality": hq / tot, "n_states": int((by_state > 0).sum()),
                "n_branches": int(len(g)), "n_certs": int(g["CERT"].nunique()),
                "top_state": by_state.idxmax(),
                "top_state_share": float(by_state.max() / tot),
            })
            got.append(int(y))
        miss = sorted(set(YEARS) - set(got))
        print(f"  {r.ticker:5s} {len(got):2d}/{len(YEARS)} vintages"
              + (f"   MISSING {miss}" if miss else ""))

    ldf = pd.DataFrame(out).sort_values(["ticker", "year"])
    ldf.to_csv("h10b_locality.csv", index=False)

    print("\n" + "=" * 74)
    print("LOCALITY BY BANK (HQ-state share of deposits) -- review before proceeding")
    print("=" * 74)
    summ = (ldf.groupby("ticker")
              .agg(hq=("hq_state", "first"), loc_mean=("locality", "mean"),
                   loc_first=("locality", "first"), loc_last=("locality", "last"),
                   states_last=("n_states", "last"), max_certs=("n_certs", "max"),
                   top_first=("top_state", "first"), top_state=("top_state", "last"),
                   vintages=("year", "count"))
              .sort_values("loc_mean"))
    print(summ.round(3).to_string())

    print("\nchecks:")
    print(f"  locality outside [0,1]: {int(((ldf.locality < 0) | (ldf.locality > 1)).sum())}")

    # A bank with deposits but NONE in its own headquarters state is not a
    # real bank, it is an entity mismatch: the charter being measured is not
    # the franchise the equity series tracks. This is what exposed NYCB being
    # resolved to the pre-2022 Michigan Flagstar thrift. Treated as fatal.
    zero_hq = ldf[(ldf.total_deposits_k > 0) & (ldf.hq_state_deposits_k <= 0)]
    print(f"  bank-years with ZERO deposits in their own HQ state: {len(zero_hq)}")
    if len(zero_hq):
        print(zero_hq[["ticker", "year", "hq_state", "top_state",
                       "total_deposits_k"]].to_string(index=False))
    mismatch = sorted(set(ldf[ldf.hq_state != ldf.top_state].ticker))
    print(f"  HQ state is not the largest deposit state: {mismatch}")
    print(f"  banks with multiple charters in some year: "
          f"{sorted(set(ldf[ldf.n_certs > 1].ticker))}")
    incomplete = {t: int(n) for t, n in ldf.groupby('ticker').year.count().items()
                  if n < len(YEARS)}
    # report failures separately: a bank that failed outright has no rows at
    # all, so it cannot show up as "missing vintages" and the coverage line
    # alone would read clean while six banks were absent from the table
    print(f"  banks that failed to pull entirely: {failed if failed else 'none'}")
    print(f"  banks present but missing vintages: {incomplete if incomplete else 'none'}")
    print(f"  banks in table: {ldf.ticker.nunique()}/{len(BANKS)}")

    if len(zero_hq):
        sys.exit("\nSTOPPING: zero-HQ-state bank-years indicate the wrong "
                 "charter was resolved. Fix the mapping before proceeding.")

    if failed or incomplete or ldf.ticker.nunique() < len(BANKS):
        sys.exit("\nSTOPPING: incomplete coverage. Rerun to resume from cache "
                 "(nothing already downloaded is refetched).")

    print("\nwrote h10b_fdic_resolution.csv and h10b_locality.csv")
    print("NO returns computed. Review both files before running the H10b backtest.")


if __name__ == "__main__":
    main()
