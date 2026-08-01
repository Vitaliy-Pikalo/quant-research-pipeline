"""
beige_book_patch_v7.py -- targeted patch for the 3 remaining gaps in
beige_book_sentiment_v6.csv. Reprocesses 3 releases, not all 131.

GAP 1+2: releases 20110302 and 20150304 are published under an 8-digit
date URL but use the 2011-2016 "First District--Boston" section format.
v6's 8-digit branch only tried the heading-based parser, so both failed.
Fix: try the old-format parser on those pages too.

GAP 3: release 201903 is missing St. Louis. Cause is a Fed-side markup
inconsistency -- that one release writes

    <h4>St. Louis</h4>

while every other district in every other release writes

    <h4>Federal Reserve Bank of St. Louis</h4>

The obvious fix -- accept bare district names as headings -- is WRONG and
would quietly corrupt 21 releases. The 2024+ template renders the short
"Highlights by Federal Reserve District" blurbs as bare-name headings
(<h5>Boston</h5>, ~60 words) which appear BEFORE the full district
reports. Since the parser takes the first heading per district, a bare-
name rule would substitute the 60-word highlight blurb for the ~650-word
district report in every split-format release. Word count would drop by
an order of magnitude and the sentiment score would be computed on a
different kind of text entirely.

So the fix is positional: a bare-name heading is only accepted if it sits
BETWEEN the headings of that district's canonical neighbours. In 201903,
"St. Louis" is accepted because it falls between Chicago and Minneapolis.
A highlights blurb near the top of the page falls outside that window and
is rejected.

RUN THIS LOCALLY.
    python beige_book_patch_v7.py

Input:  beige_book_sentiment_v6.csv
Output: beige_book_sentiment_final.csv
"""
import re
import time
from datetime import datetime

import pandas as pd
import pysentiment2 as ps
import requests

lm = ps.LM()

DISTRICTS = [
    ("Boston", "First District--Boston"),
    ("New York", "Second District--New York"),
    ("Philadelphia", "Third District--Philadelphia"),
    ("Cleveland", "Fourth District--Cleveland"),
    ("Richmond", "Fifth District--Richmond"),
    ("Atlanta", "Sixth District--Atlanta"),
    ("Chicago", "Seventh District--Chicago"),
    ("St. Louis", "Eighth District--St. Louis"),
    ("Minneapolis", "Ninth District--Minneapolis"),
    ("Kansas City", "Tenth District--Kansas City"),
    ("Dallas", "Eleventh District--Dallas"),
    ("San Francisco", "Twelfth District--San Francisco"),
]
NAMES = [d[0] for d in DISTRICTS]
ALIASES = {n.lower(): n for n in NAMES}
ALIASES.update({"st louis": "St. Louis", "saint louis": "St. Louis", "st.louis": "St. Louis"})

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research script"}
BASE = "https://www.federalreserve.gov"
MIN_WORDS, MAX_WORDS = 100, 6000
SECTION_FOOTERS = ["Back to Top", "Last Update:", "Last update:", "Return to top",
                   "Board of Governors of the Federal Reserve System 20th"]
DOC_FOOTERS = ["Last Update:", "Last update:", "Board of Governors of the Federal Reserve System 20th"]


def get(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
    except requests.RequestException:
        return None
    return r.text if r.status_code == 200 else None


def strip_html(html):
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#8217;", "'")
    t = t.replace("&rsquo;", "'").replace("&#39;", "'").replace("&#8220;", '"').replace("&#8221;", '"')
    t = re.sub(r"&#?\w+;", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def trim(text, markers):
    cut = len(text)
    for m in markers:
        i = text.find(m)
        if i != -1:
            cut = min(cut, i)
    return text[:cut].strip()


def ok_len(b):
    return MIN_WORDS <= len(b.split()) <= MAX_WORDS


def score(text):
    tok = lm.tokenize(text)
    s = lm.get_score(tok)
    return {"polarity": s["Polarity"], "subjectivity": s["Subjectivity"],
            "positive_count": s["Positive"], "negative_count": s["Negative"],
            "word_count": len(tok)}


HEAD_RE = re.compile(r"<h([1-5])\b[^>]*>(.*?)</h\1>", re.S | re.I)
PDF_RE = re.compile(r"files/BeigeBook_(\d{8})\.pdf", re.I)


def _canon(label, require_prefix):
    if require_prefix and "Federal Reserve Bank of" not in label:
        return None
    low = re.sub(r"[^a-z. ]", "", label.lower()).strip()
    for alias, canon in ALIASES.items():
        if low.endswith(alias):
            return canon
    return None


def parse_headings_gapfilled(html):
    """Prefixed headings first; then fill missing districts with bare-name
    headings, but ONLY where they fall between canonical neighbours."""
    heads = [(m.start(), m.end(), strip_html(m.group(2))) for m in HEAD_RE.finditer(html)]

    strict = {}
    for _, end, label in heads:
        c = _canon(label, require_prefix=True)
        if c:
            strict.setdefault(c, end)

    missing = [n for n in NAMES if n not in strict]
    for name in missing:
        i = NAMES.index(name)
        lo = max((strict[NAMES[j]] for j in range(i - 1, -1, -1) if NAMES[j] in strict), default=None)
        hi = min((strict[NAMES[j]] for j in range(i + 1, len(NAMES)) if NAMES[j] in strict), default=None)
        for _, end, label in heads:
            if _canon(label, require_prefix=False) != name:
                continue
            if lo is not None and end <= lo:
                continue
            if hi is not None and end >= hi:
                continue
            strict[name] = end
            print(f"    gap-filled {name} via bare-name heading at {end}")
            break

    if len(strict) < 10:
        return {}
    ordered = sorted(strict.items(), key=lambda kv: kv[1])
    out = {}
    for i, (name, a) in enumerate(ordered):
        b = ordered[i + 1][1] if i + 1 < len(ordered) else len(html)
        body = trim(strip_html(html[a:b]), SECTION_FOOTERS)
        if ok_len(body):
            out[name] = body
    return out


def parse_old(html):
    text = trim(strip_html(html), DOC_FOOTERS)
    out = {}
    for i, (name, hdr) in enumerate(DISTRICTS):
        a = text.find(hdr)
        if a == -1:
            continue
        b = len(text)
        if i + 1 < len(DISTRICTS):
            n = text.find(DISTRICTS[i + 1][1], a)
            if n != -1:
                b = n
        body = trim(text[a + len(hdr):b].strip(), SECTION_FOOTERS)
        if ok_len(body):
            out[name] = body
    return out


def date_of(html, url_date):
    m = PDF_RE.search(html or "")
    if m:
        return datetime.strptime(m.group(1), "%Y%m%d").strftime("%Y-%m-%d")
    return datetime.strptime(url_date, "%Y%m%d").strftime("%Y-%m-%d")


TARGETS = [("20110302", "201103"), ("20150304", "201503")]


def main():
    df = pd.read_csv("beige_book_sentiment_v6.csv", dtype={"release_stem": str})
    print(f"v6 in: {len(df)} rows, {df.release_stem.nunique()} releases")
    new = []

    # --- gaps 1 & 2: 8-digit URL, old-format body ---
    for d8, stem in TARGETS:
        html = get(f"{BASE}/monetarypolicy/beigebook{d8}.htm")
        if not html:
            print(f"  {d8}: page not reachable")
            continue
        d = parse_headings_gapfilled(html)
        layout = "fullrp"
        if len(d) < 10:
            d = parse_old(html)
            layout = "old"
        if len(d) < 10:
            print(f"  {d8}: still unparseable ({len(d)} districts)")
            continue
        date = date_of(html, d8)
        for name, body in d.items():
            new.append({"release_date": date, "release_stem": stem, "district": name,
                        "source_format": layout, **score(body)})
        print(f"  RECOVERED {d8} -> {date} ({layout}, {len(d)} districts)")
        time.sleep(0.3)

    # --- gap 3: 201903 missing St. Louis ---
    html = get(f"{BASE}/monetarypolicy/beigebook201903.htm")
    if html:
        d = parse_headings_gapfilled(html)
        have = set(df[df.release_stem == "201903"].district)
        date = df[df.release_stem == "201903"].release_date.iloc[0]
        for name, body in d.items():
            if name not in have:
                new.append({"release_date": date, "release_stem": "201903", "district": name,
                            "source_format": "single_page", **score(body)})
                print(f"  RECOVERED 201903 / {name} ({len(body.split())} words)")

    if new:
        df = pd.concat([df, pd.DataFrame(new)], ignore_index=True)
    df = df.drop_duplicates(subset=["release_stem", "district"], keep="first")
    df = df.sort_values(["release_date", "district"]).reset_index(drop=True)
    df.to_csv("beige_book_sentiment_final.csv", index=False)

    d = pd.to_datetime(df.release_date)
    print("\n================ FINAL QC ================")
    print(f"rows {len(df)} | releases {df.release_stem.nunique()} | span {d.min().date()} -> {d.max().date()}")
    print("\nreleases per year:")
    print(df.assign(y=df.release_stem.str[:4]).groupby("y").release_stem.nunique().to_string())
    nw = df.drop_duplicates("release_stem")
    nw = nw[pd.to_datetime(nw.release_date).dt.day_name() != "Wednesday"]
    print(f"\nnon-Wednesday: {len(nw)}")
    dc = df.groupby("release_stem").district.nunique()
    print(f"releases with <12 districts: {(dc < 12).sum()}")
    if (dc < 12).any():
        print(dc[dc < 12].to_string())
    print("\nword_count by layout:")
    print(df.groupby("source_format").word_count.agg(["count", "mean", "std", "min", "max"]).round(0).to_string())
    print("\nwrote beige_book_sentiment_final.csv")


if __name__ == "__main__":
    main()
