"""
backtests/h11_eps_tag_analysis.py -- standalone EPS tag distribution and
Basic-EPS-impact analysis, for the research question raised by the second
H11 Phase 0 probe run: is the 40.8% tag-name-based custom-tag rate real
data-quality risk, or mostly EarningsPerShareBasic (a standard us-gaap tag,
just not in EPS_TAG_PRIORITY) being miscounted as custom?

THIS SCRIPT DOES NOT MODIFY ANY PRODUCTION CODE OR DECISION. It does not
touch EPS_TAG_PRIORITY, extract_eps_records(), or custom_tag_fallback_rate().
Per explicit instruction, whether to widen the EPS definition to include
Basic EPS is a measurement-construct decision (it would change eligible
firms, SUE calculations, and event population, and touches
H11_PREREGISTRATION.md section 5's "diluted EPS from continuing operations"
language) -- not an engineering call this script or its author gets to make
unilaterally. This script only produces evidence: the real tag distribution,
a tag-by-tag classification (diluted / basic / combined / share-count-or-
other / pro-forma / SPAC-redemption-pattern), and a simulation of how many
additional firm-quarters would become SUE-computable if Basic EPS were
added as a third-tier fallback -- using extract_eps_records()'s EXISTING
tag_priority override parameter, not a code change, so the simulation
exercises the real, already-tested extraction logic rather than a
reimplementation of it.

Output is raw data (JSON), not a finished analysis document. Per this
project's standing workflow (Claude writes the script, the user runs it
locally, Claude reads the output), docs/H11_EPS_TAG_ANALYSIS.md gets
written FROM this script's real output, not guessed at in advance.

MUST BE RUN LOCALLY -- same network constraint as h11_data_probe.py (see
that script's docstring). Reuses the same connectors and, for direct
comparability, defaults to the same CIKs/quarters as the second real probe
run, but accepts overrides.

Usage (from repo root, after `pip install -r requirements.txt`):

    python backtests/h11_eps_tag_analysis.py \\
        --ciks 0000798081 0000723603 0000080420 \\
        --quarters 2020q1 2020q2 2020q3 2020q4 2021q1 2021q2 2021q3 2021q4 2022q1 2022q2 2022q3

Outputs, all under data/h11_eps_tag_analysis/:
    tag_distribution.json    top 50 EPS-like tags, namespace, count, accepted
    tag_classification.json  per-tag category + aggregated percentages
    basic_eps_impact.json    per-CIK before/after SUE-computability simulation
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # allow running as a script

from data_connectors.sec_financial_statement_datasets import (
    EPS_TAG_PRIORITY,
    extract_eps_records,
    fetch_quarter,
    tag_distribution_diagnostics,
)
from hypotheses.h11_pead.config import H11Config
from hypotheses.h11_pead.event_generator import compute_sue

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "h11_eps_tag_analysis"

# The candidate expansion under investigation. NOT applied to production
# code anywhere -- passed explicitly to extract_eps_records()'s existing
# tag_priority override, which already supports this without any change to
# the function or to EPS_TAG_PRIORITY itself.
CANDIDATE_EXPANDED_PRIORITY = [*EPS_TAG_PRIORITY, "EarningsPerShareBasic"]


def classify_tag(tag: str) -> str:
    """
    A judgment-call heuristic, offered as a starting point for reviewing
    tag_distribution.json's top_tags list -- NOT a definitive taxonomy.
    Categories, in priority order (first match wins):
      - share_count_or_exclusion_not_an_eps_value: tags that LOOK EPS-
        related by name (they contain "EarningsPerShare") but describe a
        share count, an antidilutive-securities exclusion, or a similar
        non-EPS-value concept -- these inflate the "EPS-like facts"
        denominator without representing an actual reported EPS figure.
      - pro_forma: pro-forma EPS disclosures, a different (unaudited,
        hypothetical) construct from the as-reported GAAP figure this
        design's SUE calculation is built on.
      - spac_redemption_pattern: the "subject to possible redemption" /
        "temporary equity" family, concentrated in SPAC accounting per the
        second probe run's custom_tag_examples.
      - combined_basic_and_diluted: already in EPS_TAG_PRIORITY as the
        fallback tier -- included here for completeness of the
        distribution, not because it's under question.
      - diluted_only: candidate "true diluted EPS" tags beyond the single
        currently-accepted EarningsPerShareDiluted.
      - basic_only: candidate Basic EPS tags -- this is the population the
        Basic-EPS-impact simulation is actually about.
      - other_eps_related: anything else matching "EarningsPerShare" that
        doesn't fit the above -- worth a manual look if this bucket is
        large.
    """
    name = tag.lower()
    compact = name.replace("_", "").replace("-", "").replace(" ", "")

    if ("weightedaverage" in compact or "antidilutivesecurities" in compact or
            ("securities" in compact and "excluded" in compact)):
        return "share_count_or_exclusion_not_an_eps_value"
    if "proforma" in compact:
        return "pro_forma"
    if "redemption" in compact or "temporaryequity" in compact:
        return "spac_redemption_pattern"
    if "basicanddiluted" in compact or ("basic" in compact and "diluted" in compact):
        return "combined_basic_and_diluted"
    if "diluted" in compact and "basic" not in compact:
        return "diluted_only"
    if "basic" in compact and "diluted" not in compact:
        return "basic_only"
    return "other_eps_related"


def build_tag_classification(tag_diag: dict) -> dict:
    """
    Aggregates tag_distribution_diagnostics()'s top_tags list (already
    real counts from the live data) by classify_tag() category, weighted
    by count -- this is where "percentage of true diluted EPS tags" /
    "percentage of basic EPS tags" / "percentage of irrelevant EPS-related
    tags" actually get computed, from real frequencies, not guessed.
    """
    rows = []
    total = 0
    category_counts: dict[str, int] = {}
    for row in tag_diag.get("top_tags", []):
        category = classify_tag(row["tag"])
        rows.append({**row, "category": category})
        category_counts[category] = category_counts.get(category, 0) + row["count"]
        total += row["count"]

    percentages = {cat: (count / total if total else None) for cat, count in category_counts.items()}
    return {
        "n_facts_covered_by_top_tags": total,
        "n_facts_in_full_population": tag_diag.get("n_eps_like_facts"),
        "coverage_of_full_population": (total / tag_diag["n_eps_like_facts"]) if tag_diag.get("n_eps_like_facts") else None,
        "category_counts": category_counts,
        "category_percentages": percentages,
        "per_tag_classification": rows,
    }


def simulate_expanded_tag_priority(
    sub_all: pd.DataFrame, num_all: pd.DataFrame, config: H11Config, ciks: list[str]
) -> list[dict]:
    """
    Runs the REAL extract_eps_records() twice -- once with the current
    EPS_TAG_PRIORITY, once with CANDIDATE_EXPANDED_PRIORITY -- over the
    exact same bulk data, then runs the REAL compute_sue() on each firm's
    resulting EPS history under both scenarios. Reports, per CIK: how many
    quarters of history each scenario found, whether SUE was computable
    under each, and specifically whether adding Basic EPS would make SUE
    newly computable for a firm that couldn't clear the history bar before.
    This is the actual mechanism-level answer to "how many events would be
    affected," not an estimate.

    Deliberately restricted to `ciks` (the attempted small-cap CIKs), not
    every filer in the bulk quarter data -- the bulk pull covers every
    XBRL filer regardless of size (mega-caps, ETFs, trusts), which is not
    representative of H11's $50M-$2B target universe and would require a
    market-cap join this script doesn't have to filter correctly. Keeping
    this scoped to known small-caps keeps the per-CIK detail readable and
    avoids implying a population-wide claim this script can't actually
    support.
    """
    baseline = extract_eps_records(sub_all, num_all, tag_priority=EPS_TAG_PRIORITY)
    expanded = extract_eps_records(sub_all, num_all, tag_priority=CANDIDATE_EXPANDED_PRIORITY)

    padded_ciks = [c.zfill(10) for c in ciks]
    results = []
    for cik in padded_ciks:
        baseline_eps = baseline[baseline["cik"] == cik].set_index("period_end")["eps_value"].sort_index()
        expanded_eps = expanded[expanded["cik"] == cik].set_index("period_end")["eps_value"].sort_index()

        baseline_sue, baseline_diag = (
            compute_sue(baseline_eps, config) if not baseline_eps.empty else (None, {"reason": "no_eps_records_for_cik"})
        )
        expanded_sue, expanded_diag = (
            compute_sue(expanded_eps, config) if not expanded_eps.empty else (None, {"reason": "no_eps_records_for_cik"})
        )

        results.append(
            {
                "cik": cik,
                "baseline_n_quarters": int(len(baseline_eps)),
                "expanded_n_quarters": int(len(expanded_eps)),
                "baseline_sue_computable": baseline_sue is not None,
                "expanded_sue_computable": expanded_sue is not None,
                "newly_computable_under_expanded_tags": (baseline_sue is None) and (expanded_sue is not None),
                "baseline_sue_value": baseline_sue,
                "expanded_sue_value": expanded_sue,
                "baseline_disqualification_reason": baseline_diag.get("reason"),
            }
        )
    return results


def analyze(ciks: list[str], quarters: list[str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    config = H11Config()
    session = requests.Session()

    sub_frames, num_frames = [], []
    for q in quarters:
        sub_df, num_df = fetch_quarter(q, session=session)
        sub_frames.append(sub_df)
        num_frames.append(num_df)
    sub_all = pd.concat(sub_frames, ignore_index=True) if sub_frames else pd.DataFrame()
    num_all = pd.concat(num_frames, ignore_index=True) if num_frames else pd.DataFrame()

    if num_all.empty:
        print("No data retrieved for the requested quarters -- nothing to analyze.")
        return

    tag_diag = tag_distribution_diagnostics(num_all, top_n=50)
    with open(OUT_DIR / "tag_distribution.json", "w") as f:
        json.dump(tag_diag, f, indent=2, default=str)

    classification = build_tag_classification(tag_diag)
    with open(OUT_DIR / "tag_classification.json", "w") as f:
        json.dump(classification, f, indent=2, default=str)

    impact = simulate_expanded_tag_priority(sub_all, num_all, config, ciks)
    newly_computable = sum(1 for r in impact if r["newly_computable_under_expanded_tags"])
    impact_summary = {
        "ciks_analyzed": len(impact),
        "newly_sue_computable_under_expanded_tags": newly_computable,
        "per_cik_detail": impact,
    }
    with open(OUT_DIR / "basic_eps_impact.json", "w") as f:
        json.dump(impact_summary, f, indent=2, default=str)

    print("=== EPS tag distribution ===")
    print(f"n_eps_like_facts (full population): {tag_diag['n_eps_like_facts']}")
    print(f"tag_name_based_custom_rate: {tag_diag['tag_name_based_custom_rate']:.1%}")
    print(f"namespace_based_custom_rate: {tag_diag['namespace_based_custom_rate']:.1%}")
    print()
    print("=== Category breakdown (of the top-50 tags analyzed, "
          f"covering {classification['coverage_of_full_population']:.1%} of all EPS-like facts) ===")
    for cat, pct in sorted(classification["category_percentages"].items(), key=lambda kv: -kv[1]):
        print(f"  {cat}: {pct:.1%} ({classification['category_counts'][cat]} facts)")
    print()
    print("=== Basic-EPS-as-third-tier-fallback impact simulation ===")
    print(f"CIKs analyzed: {impact_summary['ciks_analyzed']}")
    print(f"Newly SUE-computable if Basic EPS were added: {newly_computable}")
    print(f"\nFull output written under {OUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ciks", nargs="+", required=True, help="e.g. 0000798081 0000723603 0000080420")
    parser.add_argument("--quarters", nargs="+", required=True, help="e.g. 2020q1 2020q2 ... 2022q3")
    args = parser.parse_args()
    analyze(args.ciks, args.quarters)
