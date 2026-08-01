"""
beige_book_pull_v6.py -- Beige Book scraper, five layouts, one extraction rule.

CHANGES FROM v5 (and why)
-------------------------
1. parse_old() no longer trims footers on the WHOLE document.
   v5 added "Return to top" to the footer markers so the legacy parser
   would work. The 2011-2016 pages have "Return to top" links BETWEEN
   district sections, so trimming the whole document cut it off before
   the first district header and all 46 of those releases failed. v6
   locates sections on untrimmed text and trims each section body
   individually.

2. Fifth URL shape: some releases are published under an 8-DIGIT date
   rather than a 6-digit stem, e.g.
       /monetarypolicy/beigebook20230531.htm
   Their -summary.htm page exists (so they get discovered) but the
   6-digit "about" page does not, and they have no per-district pages,
   so v5 found them and then failed every parser. v6 reads the
   "Full Report" link out of the summary page and parses that. This is
   a general fix, not three hardcoded special cases -- it covers
   201103, 201503 and 202305.

3. Tolerant district-name matching ("St. Louis" / "St Louis" /
   "Saint Louis"), which recovers the single missing district in 201903.

TEXT EXTRACTION -- THE THING THAT MATTERS MOST
----------------------------------------------
Every district-release is reduced to *article text only*, by the same
rule in every era: start at that district's own heading, stop at the
page footer. Never score a whole page.

This is not fussiness. In v4 the 2024-2026 pages were scored whole, so
~850 words of identical site-navigation boilerplate went into every
score. Word counts ran 1496 vs 640 elsewhere and polarity variance fell
~40%. That is a structural break in the series at the exact date the Fed
changed its template, and a district-relative z-score would have read it
as a real, simultaneous, cross-district sentiment shift. A backtest can
absolutely "find" that. It would be an artifact of my scraper.

FIVE LAYOUTS
------------
  LEGACY (2010-2011):  /fomc/beigebook/{yyyy}/{yyyymmdd}/{1..12}.htm
  OLD    (2011-2016):  /monetarypolicy/beigebook/beigebook{stem}.htm
  SINGLE (2017-2023):  /monetarypolicy/beigebook{stem}.htm
  FULLRP (odd ones):   /monetarypolicy/beigebook{yyyymmdd}.htm
  SPLIT  (2024-2026):  /monetarypolicy/beigebook{stem}-{slug}.htm

DATES: files/BeigeBook_YYYYMMDD.pdf > 8-digit URL > legacy URL > title.
Validated against the fact that every Beige Book publishes on a Wednesday.

RUN THIS LOCALLY.
    pip install requests pysentiment2 pandas
    python beige_book_pull_v6.py

Output: beige_book_sentiment_v6.csv, beige_book_v6_report.csv
"""
import re
import time
from datetime import datetime

import pandas as pd
import pysentiment2 as ps
import requests

lm = ps.LM()

DISTRICTS = [
    ("Boston", "boston", "First District--Boston"),
    ("New York", "new-york", "Second District--New York"),
    ("Philadelphia", "philadelphia", "Third District--Philadelphia"),
    ("Cleveland", "cleveland", "Fourth District--Cleveland"),
    ("Richmond", "richmond", "Fifth District--Richmond"),
    ("Atlanta", "atlanta", "Sixth District--Atlanta"),
    ("Chicago", "chicago", "Seventh District--Chicago"),
    ("St. Louis", "st-louis", "Eighth District--St. Louis"),
    ("Minneapolis", "minneapolis", "Ninth District--Minneapolis"),
    ("Kansas City", "kansas-city", "Tenth District--Kansas City"),
    ("Dallas", "dallas", "Eleventh District--Dallas"),
    ("San Francisco", "san-francisco", "Twelfth District--San Francisco"),
]
NAMES = [d[0] for d in DISTRICTS]

# tolerant aliases -> canonical name
ALIASES = {}
for n in NAMES:
    ALIASES[n.lower()] = n
ALIASES.update({
    "st louis": "St. Louis", "saint louis": "St. Louis", "st.louis": "St. Louis",
    "newyork": "New York", "kansascity": "Kansas City", "sanfrancisco": "San Francisco",
})

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research script"}
BASE = "https://www.federalreserve.gov"
OUT_CSV = "beige_book_sentiment_v6.csv"
REPORT_CSV = "beige_book_v6_report.csv"

YEARS = range(2010, 2027)
MIN_DISTRICTS = 10
MIN_WORDS = 100
MAX_WORDS = 6000
SLEEP = 0.12

# markers safe to cut at when we already hold a SINGLE district's slice
SECTION_FOOTERS = ["Back to Top", "Last Update:", "Last update:", "Return to top",
                   "Board of Governors of the Federal Reserve System 20th"]
# markers safe to cut at on a WHOLE multi-district document
DOC_FOOTERS = ["Last Update:", "Last update:",
               "Board of Governors of the Federal Reserve System 20th"]


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
    t = t.replace("&nbsp;", " ").replace("&amp;", "&")
    t = t.replace("&#8217;", "'").replace("&rsquo;", "'").replace("&#39;", "'")
    t = t.replace("&#8220;", '"').replace("&#8221;", '"').replace("&quot;", '"')
    t = re.sub(r"&#?\w+;", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def trim(text, markers):
    cut = len(text)
    for m in markers:
        i = text.find(m)
        if i != -1:
            cut = min(cut, i)
    return text[:cut].strip()


def ok_len(body):
    return MIN_WORDS <= len(body.split()) <= MAX_WORDS


PDF_RE = re.compile(r"files/BeigeBook_(\d{8})\.pdf", re.I)
FULLRP_RE = re.compile(r"beigebook(\d{8})\.htm", re.I)
TITLE_DATE = re.compile(r"([A-Z][a-z]+ \d{1,2},\s*\d{4})")


def date_from(html, url_date=None):
    if html:
        m = PDF_RE.search(html)
        if m:
            try:
                return datetime.strptime(m.group(1), "%Y%m%d").strftime("%Y-%m-%d"), "pdf_link"
            except ValueError:
                pass
    if url_date:
        try:
            return datetime.strptime(url_date, "%Y%m%d").strftime("%Y-%m-%d"), "url_date"
        except ValueError:
            pass
    if html:
        t = re.search(r"<title>(.*?)</title>", html, flags=re.S | re.I)
        for blob in ([strip_html(t.group(1))] if t else []) + [strip_html(html)[:4000]]:
            d = TITLE_DATE.search(blob)
            if d:
                try:
                    return datetime.strptime(re.sub(r"\s+", " ", d.group(1)), "%B %d, %Y").strftime("%Y-%m-%d"), "title"
                except ValueError:
                    continue
    return None, None


def score(text):
    tok = lm.tokenize(text)
    s = lm.get_score(tok)
    return {"polarity": s["Polarity"], "subjectivity": s["Subjectivity"],
            "positive_count": s["Positive"], "negative_count": s["Negative"],
            "word_count": len(tok)}


# ---------------- discovery ----------------

def discover():
    found = {}
    for year in YEARS:
        for url in (f"{BASE}/monetarypolicy/beigebook{year}.htm", f"{BASE}/fomc/beigebook/{year}/"):
            idx = get(url)
            if not idx:
                continue
            for d8 in set(re.findall(r"beigebook(\d{8})\.htm", idx)):
                if d8.startswith(str(year)):
                    found.setdefault(d8, ("fullrp", d8))
            for d8 in set(re.findall(r"/fomc/beigebook/\d{4}/(\d{8})/", idx)) | \
                      set(re.findall(r"(\d{8})/default\.htm", idx)):
                found[d8] = ("legacy", d8)
            for stem in set(re.findall(r"beigebook(\d{6})(?:[-.])", idx)):
                if stem.startswith(str(year)):
                    found.setdefault(stem, ("stem", stem))
            time.sleep(SLEEP)

    for year in YEARS:
        for month in range(1, 13):
            stem = f"{year}{month:02d}"
            if any(k.startswith(stem) for k in found):
                continue
            if get(f"{BASE}/monetarypolicy/beigebook{stem}-summary.htm") or \
               get(f"{BASE}/monetarypolicy/beigebook{stem}.htm") or \
               get(f"{BASE}/monetarypolicy/beigebook/beigebook{stem}.htm"):
                found[stem] = ("stem", stem)
            time.sleep(0.06)

    legacy_months = {v[1][:6] for v in found.values() if v[0] == "legacy"}
    for k in list(found):
        if found[k][0] != "legacy" and k[:6] in legacy_months and len(k) == 6:
            del found[k]
    return found


# ---------------- parsers ----------------

def parse_legacy(d8):
    out, first_html = {}, None
    for i, (name, _, _) in enumerate(DISTRICTS, start=1):
        html = get(f"{BASE}/fomc/beigebook/{d8[:4]}/{d8}/{i}.htm")
        if not html:
            continue
        first_html = first_html or html
        text = strip_html(html)
        j = text.find("Full report")           # district nav list ends here
        if j != -1:
            text = text[j + len("Full report"):]
        body = trim(text, SECTION_FOOTERS)
        if ok_len(body):
            out[name] = body
        time.sleep(SLEEP)
    return out, first_html


def parse_old(html):
    """2011-2016. Sections located on UNTRIMMED text; each body trimmed
    individually. Trimming the whole document first is what broke v5."""
    text = trim(strip_html(html), DOC_FOOTERS)
    out = {}
    for i, (name, _, hdr) in enumerate(DISTRICTS):
        a = text.find(hdr)
        if a == -1:
            continue
        b = len(text)
        if i + 1 < len(DISTRICTS):
            n = text.find(DISTRICTS[i + 1][2], a)
            if n != -1:
                b = n
        body = trim(text[a + len(hdr):b].strip(), SECTION_FOOTERS)
        if ok_len(body):
            out[name] = body
    return out


HEAD_RE = re.compile(r"<h([1-5])\b[^>]*>(.*?)</h\1>", re.S | re.I)


def _canon(label):
    low = re.sub(r"[^a-z. ]", "", label.lower()).strip()
    for alias, canon in ALIASES.items():
        if low.endswith(alias):
            return canon
    return None


def _heading_marks(html):
    marks = []
    for m in HEAD_RE.finditer(html):
        label = strip_html(m.group(2))
        if "Federal Reserve Bank of" not in label:
            continue
        c = _canon(label)
        if c:
            marks.append((m.end(), c))
    return marks


def parse_headings(html):
    marks = _heading_marks(html)
    if len(marks) < MIN_DISTRICTS:
        return {}
    first = {}
    for pos, name in marks:
        first.setdefault(name, pos)
    ordered = sorted(first.items(), key=lambda kv: kv[1])
    out = {}
    for i, (name, a) in enumerate(ordered):
        b = ordered[i + 1][1] if i + 1 < len(ordered) else len(html)
        body = trim(strip_html(html[a:b]), SECTION_FOOTERS)
        if ok_len(body):
            out[name] = body
    return out


def parse_split(stem):
    out = {}
    for name, slug, _ in DISTRICTS:
        html = get(f"{BASE}/monetarypolicy/beigebook{stem}-{slug}.htm")
        if html:
            marks = _heading_marks(html)
            if marks:
                body = trim(strip_html(html[marks[0][0]:]), SECTION_FOOTERS)
                if ok_len(body):
                    out[name] = body
        time.sleep(SLEEP)
    return out


# ---------------- main ----------------

def main():
    print("discovering...")
    found = discover()
    print(f"{len(found)} candidate releases\n")

    rows, report = [], []
    for key in sorted(found):
        kind, ident = found[key]
        districts, layout, hdate, udate = {}, None, None, None

        if kind == "legacy":
            districts, hdate = parse_legacy(ident)
            layout, udate, stem = "legacy", ident, ident[:6]
        elif kind == "fullrp":
            html = get(f"{BASE}/monetarypolicy/beigebook{ident}.htm")
            hdate, udate, stem = html, ident, ident[:6]
            if html:
                d = parse_headings(html)
                if len(d) >= MIN_DISTRICTS:
                    districts, layout = d, "fullrp"
        else:
            stem = ident
            about = get(f"{BASE}/monetarypolicy/beigebook{stem}.htm")
            summary = get(f"{BASE}/monetarypolicy/beigebook{stem}-summary.htm")
            hdate = about or summary

            if summary:
                d = parse_split(stem)
                if len(d) >= MIN_DISTRICTS:
                    districts, layout = d, "split"
            if not districts and about:
                d = parse_headings(about)
                if len(d) >= MIN_DISTRICTS:
                    districts, layout = d, "single_page"
            if not districts and summary:
                # 8-digit "Full Report" link lives on the summary page
                m = FULLRP_RE.search(summary)
                if m:
                    full = get(f"{BASE}/monetarypolicy/beigebook{m.group(1)}.htm")
                    if full:
                        hdate, udate = full, m.group(1)
                        d = parse_headings(full)
                        if len(d) >= MIN_DISTRICTS:
                            districts, layout = d, "fullrp"
            if not districts:
                old = get(f"{BASE}/monetarypolicy/beigebook/beigebook{stem}.htm")
                if old:
                    hdate = hdate or old
                    d = parse_old(old)
                    if len(d) >= MIN_DISTRICTS:
                        districts, layout = d, "old"

        date, dsrc = date_from(hdate, udate)
        if not districts:
            print(f"  FAIL {key}")
            report.append((key, date or "", "parse_failed", 0, "", ""))
            continue
        if not date:
            date, dsrc = f"{stem[:4]}-{stem[4:]}-01", "PLACEHOLDER"
            print(f"  WARN {key}: placeholder date")
        for name, body in districts.items():
            rows.append({"release_date": date, "release_stem": stem, "district": name,
                         "source_format": layout, **score(body)})
        print(f"  OK {key} -> {date} [{dsrc}] ({layout}, {len(districts)})")
        report.append((key, date, "ok", len(districts), layout, dsrc))
        time.sleep(0.2)

    df = pd.DataFrame(rows).drop_duplicates(subset=["release_stem", "district"], keep="first")
    df = df.sort_values(["release_date", "district"]).reset_index(drop=True)
    df.to_csv(OUT_CSV, index=False)
    pd.DataFrame(report, columns=["key", "date", "status", "n", "layout", "date_source"]).to_csv(REPORT_CSV, index=False)

    d = pd.to_datetime(df.release_date)
    print("\n================ QC ================")
    print(f"rows {len(df)} | releases {df.release_stem.nunique()} | span {d.min().date()} -> {d.max().date()}")
    print("\nreleases per year:")
    print(df.assign(y=df.release_stem.str[:4]).groupby("y").release_stem.nunique().to_string())
    nw = df.drop_duplicates("release_stem")
    nw = nw[pd.to_datetime(nw.release_date).dt.day_name() != "Wednesday"]
    print(f"\nnon-Wednesday releases: {len(nw)}")
    if len(nw):
        print(nw[["release_stem", "release_date"]].to_string(index=False))
    print("\nword_count by layout (must be comparable):")
    print(df.groupby("source_format").word_count.agg(["count", "mean", "std", "min", "max"]).round(0).to_string())
    print("\npolarity by layout:")
    print(df.groupby("source_format").polarity.agg(["mean", "std"]).round(4).to_string())
    dc = df.groupby("release_stem").district.nunique()
    print(f"\nreleases with <12 districts: {(dc < 12).sum()}")
    if (dc < 12).any():
        print(dc[dc < 12].to_string())
    print(f"\nwrote {OUT_CSV}, {REPORT_CSV}")


if __name__ == "__main__":
    main()
