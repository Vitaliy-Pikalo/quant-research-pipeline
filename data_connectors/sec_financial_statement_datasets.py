"""
data_connectors/sec_financial_statement_datasets.py -- SEC's bulk quarterly
XBRL "Financial Statement Data Sets" (num.txt / sub.txt), free, official,
no key.

Declared the primary as-filed EPS source in H11_PREREGISTRATION.md section
15 (amended per H11_data_availability_review.md sections 1 and 6), in
preference to per-CIK companyfacts API calls: one bulk download per quarter
covers every filer, versus ~2,000+ individual API calls to build the same
panel.

The tag-priority fallback list (EPS_TAG_PRIORITY) is the concrete
implementation of the custom-XBRL-tag risk flagged in
H11_data_availability_review.md section 1/3: not every filer tags diluted
EPS with the standard `us-gaap:EarningsPerShareDiluted` element, and lower-
quality/smaller filers are documented in the XBRL data-quality literature to
use custom extension tags more often -- exactly this design's target
universe. extract_eps_records() reports which tag was actually used per
record (H11_PREREGISTRATION.md section 13.5's custom-tag fallback-rate
check depends on this column existing, not being silently dropped).

fetch_quarter() requires network access this sandbox doesn't have (see
sec_company_tickers.py's docstring for the same caveat) -- untested here,
run locally. extract_eps_records() is pure and fully unit-tested against
fixture data matching SEC's documented sub.txt/num.txt column layout.
"""
from __future__ import annotations

import io
import zipfile

import pandas as pd
import requests

SEC_USER_AGENT = "quant-research-pipeline research@example.com"  # replace with a real contact before running live
FSDS_URL_TMPL = "https://www.sec.gov/files/dera/data/financial-statement-data-sets/{quarter}.zip"

# Priority order, highest first. Only EPS from continuing operations is
# wanted (H11_PREREGISTRATION.md section 5) -- basic-and-diluted combined
# tags are accepted as a fallback ONLY when a filer doesn't separately
# report diluted, per common small-filer XBRL practice.
EPS_TAG_PRIORITY: list[str] = [
    "EarningsPerShareDiluted",
    "EarningsPerShareBasicAndDiluted",
]

_SUB_COLUMNS_NEEDED = ["adsh", "cik", "form", "period", "fy", "fp", "filed"]
_NUM_COLUMNS_NEEDED = ["adsh", "tag", "version", "ddate", "qtrs", "uom", "value"]


def extract_eps_records(sub_df: pd.DataFrame, num_df: pd.DataFrame, tag_priority: list[str] | None = None) -> pd.DataFrame:
    """
    sub_df, num_df : already-loaded (e.g. via pd.read_csv(..., sep="\\t"))
        contents of one quarter's sub.txt / num.txt.

    Joins on adsh (the filing accession number), keeps only quarterly
    (qtrs == 1) facts tagged with one of tag_priority, and for any
    (cik, ddate) with more than one qualifying tag, keeps the
    highest-priority one -- this is the fallback logic itself.

    Returns columns: cik, period_end, eps_value, tag_used, form, filed, adsh.
    A record's tag_used column is what H11_PREREGISTRATION.md section 13.5's
    fallback-rate diagnostic is computed from -- never drop it.
    """
    tag_priority = tag_priority or EPS_TAG_PRIORITY

    missing_sub = set(_SUB_COLUMNS_NEEDED) - set(sub_df.columns)
    missing_num = set(_NUM_COLUMNS_NEEDED) - set(num_df.columns)
    if missing_sub or missing_num:
        raise ValueError(f"missing columns -- sub.txt: {missing_sub or 'ok'}, num.txt: {missing_num or 'ok'}")

    candidates = num_df[num_df["tag"].isin(tag_priority) & (num_df["qtrs"] == 1)]
    if candidates.empty:
        return pd.DataFrame(columns=["cik", "period_end", "eps_value", "tag_used", "form", "filed", "adsh"])

    merged = candidates.merge(sub_df[_SUB_COLUMNS_NEEDED], on="adsh", how="inner")

    priority_rank = {tag: i for i, tag in enumerate(tag_priority)}
    merged = merged.assign(_tag_rank=merged["tag"].map(priority_rank))
    merged = merged.sort_values(["cik", "ddate", "_tag_rank"])
    deduped = merged.drop_duplicates(subset=["cik", "ddate"], keep="first")

    out = deduped.rename(columns={"ddate": "period_end", "value": "eps_value", "tag": "tag_used"})
    out["cik"] = out["cik"].astype(str).str.zfill(10)
    out["period_end"] = pd.to_datetime(out["period_end"], format="%Y%m%d", errors="coerce")
    out["filed"] = pd.to_datetime(out["filed"], format="%Y%m%d", errors="coerce")
    return out[["cik", "period_end", "eps_value", "tag_used", "form", "filed", "adsh"]].reset_index(drop=True)


def custom_tag_fallback_rate(num_df: pd.DataFrame, standard_tags: list[str] | None = None) -> dict:
    """
    Diagnostic required by H11_PREREGISTRATION.md section 13.5: fraction of
    EPS-relevant facts using a non-standard (custom extension) tag, out of
    everything that LOOKS like it's trying to report an EPS-shaped concept
    (heuristic: tag name contains "EarningsPerShare"). This is a coarse
    diagnostic, not a filter -- it exists to be reported, not to silently
    change which records get used.
    """
    standard_tags = set(standard_tags or EPS_TAG_PRIORITY)
    eps_like = num_df[num_df["tag"].str.contains("EarningsPerShare", case=False, na=False)]
    if eps_like.empty:
        return {"n_eps_like_facts": 0, "n_standard": 0, "n_custom": 0, "custom_fallback_rate": float("nan")}
    is_standard = eps_like["tag"].isin(standard_tags)
    return {
        "n_eps_like_facts": len(eps_like),
        "n_standard": int(is_standard.sum()),
        "n_custom": int((~is_standard).sum()),
        "custom_fallback_rate": float((~is_standard).mean()),
    }


def fetch_quarter(quarter: str, session: requests.Session | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:  # pragma: no cover -- network
    """
    quarter : e.g. "2022q3", matching SEC's own file-naming convention.
    Downloads and unzips one quarter's Financial Statement Data Set,
    returning (sub_df, num_df). Requires network access this sandbox
    doesn't have -- see module docstring.
    """
    session = session or requests.Session()
    resp = session.get(FSDS_URL_TMPL.format(quarter=quarter), headers={"User-Agent": SEC_USER_AGENT}, timeout=120)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open("sub.txt") as f:
            sub_df = pd.read_csv(f, sep="\t", low_memory=False)
        with zf.open("num.txt") as f:
            num_df = pd.read_csv(f, sep="\t", low_memory=False)
    return sub_df, num_df
