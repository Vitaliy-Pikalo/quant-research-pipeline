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

from data_connectors.telemetry import RequestTelemetryCollector, instrumented_get

SEC_USER_AGENT = "Vitaliy Pikalo pikalo.vitaliy@gmail.com"  # real identifying contact per SEC's fair-access policy
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

# CORRECTED after real-data diagnostic (see backtests/_diag_shares_tags.py
# output, 2026-08-03, real 2022q3 pull): the original assumption below this
# comment was WRONG and is kept only as a record of what was tried.
#
# ORIGINAL (wrong) assumption: "EntityCommonStockSharesOutstanding" (a dei
# cover-page fact) would have near-universal coverage since it's a required
# cover-page element. Real data showed only 3 total rows in a full quarter's
# bulk file -- SEC's Financial Statement Data Sets are built from the
# financial statements themselves, not the document cover page, so a
# cover-page-only fact is barely represented here regardless of how
# "required" it is on the actual filed document.
#
# REAL primary tag, confirmed against live data: "CommonStockSharesOutstanding"
# (us-gaap, a genuine balance-sheet/equity-note disclosure) -- 27,424 rows in
# the same quarter, confirmed instant-type (qtrs == 0, same filter as
# below), and confirmed to be the tag multi-class filers repeat once per
# share class -- exactly the "sum all reported share-class tags" pattern
# H11_data_availability_review.md section 5 describes.
SHARES_OUTSTANDING_TAG_PRIORITY: list[str] = [
    "CommonStockSharesOutstanding",
    "EntityCommonStockSharesOutstanding",  # rare in this dataset (see above); kept as a low-priority fallback, not the primary source
]

# The `version` column in num.txt encodes a fact's taxonomy namespace, e.g.
# "us-gaap/2022" for a standard element or a filer-specific prefix (often
# derived from the filer's own short code) for a custom extension element.
# These are XBRL US's standard, shared taxonomies -- anything outside this
# set is a company-specific extension, which is a DIFFERENT and generally
# more reliable signal than matching on the tag NAME (see
# tag_distribution_diagnostics()'s namespace_based_custom_rate).
_STANDARD_TAXONOMY_PREFIXES = frozenset({"us-gaap", "dei", "srt", "country", "currency", "invest", "stpr", "naics", "sic", "exch"})


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


def extract_shares_outstanding(sub_df: pd.DataFrame, num_df: pd.DataFrame, tag_priority: list[str] | None = None) -> pd.DataFrame:
    """
    Extracts as-filed shares-outstanding facts for market-cap construction
    (H11_IMPLEMENTATION_SPEC.md stage 2). NOT part of EPS extraction --
    entirely separate tag family, entirely separate use (market cap /
    universe qualification, not SUE).

    Per H11_data_availability_review.md section 5's "Dual-class share
    aggregation for market cap" mitigation ("sum all reported share-class
    tags for a CIK at each date"): a filer with two share classes reports
    EntityCommonStockSharesOutstanding more than once for the SAME
    (cik, ddate, adsh) -- once per class, distinguished in num.txt by the
    `coreg` column -- and every such row must be summed, not deduplicated
    down to one. This is the opposite of extract_eps_records()'s
    keep-highest-priority-one behavior, deliberately: EPS tags compete
    (same concept, different tag names, pick the best one); share-class
    rows do not compete, they add up to total shares outstanding.

    Only sums within a single (cik, ddate, adsh) -- if the same period_end
    is reported across more than one filing (e.g. a 10-Q and a later
    10-Q/A), those are kept as separate rows (most recently FILED one
    should be preferred by the caller), never summed across filings, which
    would double-count.

    Returns columns: cik, period_end, shares_outstanding, tag_used, form,
    filed, adsh.
    """
    tag_priority = tag_priority or SHARES_OUTSTANDING_TAG_PRIORITY

    missing_sub = set(_SUB_COLUMNS_NEEDED) - set(sub_df.columns)
    missing_num = set(_NUM_COLUMNS_NEEDED) - set(num_df.columns)
    if missing_sub or missing_num:
        raise ValueError(f"missing columns -- sub.txt: {missing_sub or 'ok'}, num.txt: {missing_num or 'ok'}")

    candidates = num_df[num_df["tag"].isin(tag_priority) & (num_df["qtrs"] == 0)]
    if candidates.empty:
        return pd.DataFrame(columns=["cik", "period_end", "shares_outstanding", "tag_used", "form", "filed", "adsh"])

    # Defensive dedup on the full fact identity (including coreg, if
    # present) before summing -- protects against the same exact row
    # appearing twice in a source file, not against legitimate multi-class
    # rows, which differ by coreg and must both survive.
    dedup_subset = [c for c in ["adsh", "tag", "ddate", "coreg", "value"] if c in candidates.columns]
    candidates = candidates.drop_duplicates(subset=dedup_subset)

    merged = candidates.merge(sub_df[_SUB_COLUMNS_NEEDED], on="adsh", how="inner")

    # priority_rank picks ONE tag per (cik, ddate, adsh) if more than one
    # priority tag is present for the same filing/date; rows within that
    # chosen tag are then summed across share classes.
    priority_rank = {tag: i for i, tag in enumerate(tag_priority)}
    merged = merged.assign(_tag_rank=merged["tag"].map(priority_rank))
    best_tag_per_group = (
        merged.sort_values(["cik", "ddate", "adsh", "_tag_rank"])
        .groupby(["cik", "ddate", "adsh"], as_index=False)
        .first()[["cik", "ddate", "adsh", "tag"]]
        .rename(columns={"tag": "_chosen_tag"})
    )
    merged = merged.merge(best_tag_per_group, on=["cik", "ddate", "adsh"])
    merged = merged[merged["tag"] == merged["_chosen_tag"]]

    summed = merged.groupby(["cik", "ddate", "adsh", "form", "filed"], as_index=False).agg(
        shares_outstanding=("value", "sum"), tag_used=("tag", "first")
    )

    summed["cik"] = summed["cik"].astype(str).str.zfill(10)
    summed["period_end"] = pd.to_datetime(summed["ddate"], format="%Y%m%d", errors="coerce")
    summed["filed"] = pd.to_datetime(summed["filed"], format="%Y%m%d", errors="coerce")
    return summed[["cik", "period_end", "shares_outstanding", "tag_used", "form", "filed", "adsh"]].reset_index(drop=True)


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


def tag_distribution_diagnostics(num_df: pd.DataFrame, tag_priority: list[str] | None = None, top_n: int = 20) -> dict:
    """
    Instrumentation-only diagnostic -- does NOT change which records
    extract_eps_records() accepts or how custom_tag_fallback_rate()
    computes its rate. Added per this milestone's explicit scope: the
    first real probe reported a 52.3% custom-tag fallback rate, which is
    surprising enough that it needs to be inspected before anyone decides
    whether it reflects a real data-quality limitation or an artifact of
    the rate's own measurement heuristic. This function makes the
    underlying tag composition visible so that question can actually be
    answered, without touching the extraction rule itself.

    Returns a dict with:
      - n_eps_like_facts: same population custom_tag_fallback_rate() uses
        (tag name contains "EarningsPerShare", case-insensitive).
      - top_tags: the top_n most frequent EPS-like tags, each with its
        namespace (parsed from the `version` column's prefix before "/")
        and whether tag_priority currently accepts it.
      - custom_tag_examples: up to 10 distinct (tag, namespace) pairs among
        facts NOT in tag_priority, for manual inspection -- this is what
        the previous probe report couldn't show at all.
      - tag_name_based_custom_rate: identical definition to
        custom_tag_fallback_rate()'s rate (kept alongside for direct
        comparison, not as a replacement).
      - namespace_based_custom_rate: an ALTERNATIVE custom-tag signal using
        the `version` column's taxonomy namespace instead of the tag name.
        Standard us-gaap tags NOT in EPS_TAG_PRIORITY (e.g.
        "EarningsPerShareBasic", reported alone by filers with a simple
        capital structure) are still namespace-standard even though the
        tag-name-based rate currently counts them as "custom" -- if the two
        rates disagree substantially, that disagreement is itself the
        evidence needed to decide whether the tag-name heuristic is
        overstating the real custom-tag rate.
      - rates_agree_within_5pct: convenience flag on the above comparison.
    """
    tag_priority = tag_priority or EPS_TAG_PRIORITY
    eps_like = num_df[num_df["tag"].str.contains("EarningsPerShare", case=False, na=False)].copy()

    if eps_like.empty:
        return {
            "n_eps_like_facts": 0,
            "top_tags": [],
            "custom_tag_examples": [],
            "tag_name_based_custom_rate": None,
            "namespace_based_custom_rate": None,
            "rates_agree_within_5pct": None,
        }

    eps_like["namespace"] = eps_like["version"].astype(str).str.split("/").str[0].str.lower()
    eps_like["is_standard_taxonomy_namespace"] = eps_like["namespace"].isin(_STANDARD_TAXONOMY_PREFIXES)
    eps_like["accepted_by_tag_priority"] = eps_like["tag"].isin(tag_priority)

    tag_counts = (
        eps_like.groupby(["tag", "namespace"], dropna=False)
        .agg(count=("tag", "size"), accepted=("accepted_by_tag_priority", "first"))
        .reset_index()
        .sort_values("count", ascending=False)
        .head(top_n)
    )
    top_tags = [
        {"tag": row["tag"], "namespace": row["namespace"], "count": int(row["count"]), "accepted": bool(row["accepted"])}
        for _, row in tag_counts.iterrows()
    ]

    non_priority = eps_like[~eps_like["accepted_by_tag_priority"]]
    custom_tag_examples = non_priority[["tag", "namespace"]].drop_duplicates().head(10).to_dict(orient="records")

    tag_name_based_custom_rate = float((~eps_like["accepted_by_tag_priority"]).mean())
    namespace_based_custom_rate = float((~eps_like["is_standard_taxonomy_namespace"]).mean())

    return {
        "n_eps_like_facts": int(len(eps_like)),
        "top_tags": top_tags,
        "custom_tag_examples": custom_tag_examples,
        "tag_name_based_custom_rate": tag_name_based_custom_rate,
        "namespace_based_custom_rate": namespace_based_custom_rate,
        "rates_agree_within_5pct": abs(tag_name_based_custom_rate - namespace_based_custom_rate) <= 0.05,
    }


def fetch_quarter(
    quarter: str, session: requests.Session | None = None, telemetry: RequestTelemetryCollector | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:  # pragma: no cover -- network
    """
    quarter : e.g. "2022q3", matching SEC's own file-naming convention.
    Downloads and unzips one quarter's Financial Statement Data Set,
    returning (sub_df, num_df). Requires network access this sandbox
    doesn't have -- see module docstring.
    """
    session = session or requests.Session()
    resp = instrumented_get(
        session,
        FSDS_URL_TMPL.format(quarter=quarter),
        headers={"User-Agent": SEC_USER_AGENT},
        timeout=120,
        endpoint_label="sec_fsds_quarter",
        telemetry=telemetry,
    )
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open("sub.txt") as f:
            sub_df = pd.read_csv(f, sep="\t", low_memory=False)
        with zf.open("num.txt") as f:
            num_df = pd.read_csv(f, sep="\t", low_memory=False)
    return sub_df, num_df
