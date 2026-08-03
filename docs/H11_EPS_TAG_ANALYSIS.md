# H11 EPS Tag Analysis

**Status:** informational — no production code or `EPS_TAG_PRIORITY` change implied or made.
**Generated from:** real output of `backtests/h11_eps_tag_analysis.py`, run locally on 2026-08-02.
**Question this answers:** the second H11 Phase 0 probe measured a 40.8% "custom-tag rate" for EPS facts. Is that a real data-quality risk (companies inventing bespoke EPS tags), or mostly a labeling artifact of `EarningsPerShareBasic` — a standard `us-gaap` tag that simply isn't in `EPS_TAG_PRIORITY` yet — being counted as "custom" because it isn't on the accepted list?

## Data scope (important — two different populations)

This analysis mixes two different scopes and they should not be conflated:

- **Tag distribution / classification** (`tag_distribution.json`, `tag_classification.json`): every EPS-like XBRL fact reported by **every SEC filer** in the bulk quarterly datasets for 2020Q1–2022Q3 (`n_eps_like_facts` = 482,711). This is industry-wide — mega-caps, ETFs, trusts, everything — not filtered to H11's $50M–$2B small-cap universe.
- **Basic-EPS impact simulation** (`basic_eps_impact.json`): deliberately restricted to the 3 verified small-cap CIKs from the prior real probe (Powell Industries and two others), same 11 quarters, for direct comparability. This is the only part of this analysis that says anything about H11's actual target universe.

## Tag distribution — what's actually being tagged "custom"

| metric | value |
|---|---|
| EPS-like facts, full population | 482,711 |
| Custom-tag rate, by tag **name** heuristic (prior probe's method) | 40.8% |
| Custom-tag rate, by tag **namespace** (is it actually filed under a company-specific extension, not `us-gaap`) | 0.8% |
| Do the two methods agree within 5 points? | **No** |

The two rates disagree by a factor of ~50. That gap is almost entirely one tag:

| tag | namespace | count | % of full population | currently accepted? |
|---|---|---|---|---|
| `EarningsPerShareBasic` | `us-gaap` | 191,941 | 39.8% | No |
| `EarningsPerShareDiluted` | `us-gaap` | 183,807 | 38.1% | Yes |
| `EarningsPerShareBasicAndDiluted` | `us-gaap` | 101,737 | 21.1% | Yes (3rd-tier fallback) |
| `AntidilutiveSecuritiesExcludedFromComputationOfEarningsPerShareAmount` | `us-gaap` | 756 | 0.16% | No |
| `EarningsPerShareBasicUndistributed` | `us-gaap` | 149 | 0.03% | No |
| `EarningsPerShareDilutedUndistributed` | `us-gaap` | 114 | 0.02% | No |
| `EarningsPerShareBasicDistributed` | `us-gaap` | 86 | 0.02% | No |
| `BasicEarningsPerShareProForma` | `us-gaap` | 75 | 0.02% | No |
| `DilutedEarningsPerShareProForma` | `us-gaap` | 74 | 0.02% | No |

Below that, the long tail is dozens of one-off tags like `EarningsPerShareBasicAndDilutedSubjectToPossibleRedemption` and `TemporaryEquityEarningsPerShareBasicAndDiluted`, each filed under a filer-specific accession-number namespace (e.g. `0001493152-21-014216`) rather than `us-gaap`, each contributing single or double-digit fact counts. These are genuine custom extensions — and per the classification heuristic below, they cluster in SPAC/redeemable-equity accounting, consistent with what the prior probe's `custom_tag_examples` already flagged.

**Read on the 40.8% figure:** the name-based method counts `EarningsPerShareBasic` as "custom" purely because it isn't in `EPS_TAG_PRIORITY`, not because it's a company-invented tag. By namespace — the actual technical definition of a custom extension — only 0.8% of facts are custom. Most of the apparent "custom tag risk" from the prior probe is this one standard, common tag sitting outside the current allow-list, not bespoke company tagging.

## Category breakdown (top-50 tags, 99.4% coverage of the full population)

| category | % of facts | count | what it means |
|---|---|---|---|
| `basic_only` | 40.1% | 192,201 | Basic EPS variants — headline is `EarningsPerShareBasic` |
| `diluted_only` | 38.4% | 183,935 | Diluted EPS variants — headline is `EarningsPerShareDiluted` (already accepted) |
| `combined_basic_and_diluted` | 21.3% | 101,966 | Already accepted as the 3rd-tier fallback |
| `share_count_or_exclusion_not_an_eps_value` | 0.16% | 756 | Not actually an EPS figure (antidilutive-securities exclusion amount) |
| `spac_redemption_pattern` | 0.11% | 550 | SPAC/temporary-equity redemption-related EPS variants |
| `pro_forma` | 0.04% | 184 | Pro-forma (unaudited/hypothetical) EPS, a different construct from as-reported GAAP EPS |

So: of all EPS-like tags in the bulk data, roughly 40% are genuinely diluted, roughly 40% are genuinely basic, and well under 1% are irrelevant-to-EPS or a fundamentally different construct (pro-forma, SPAC redemption). The "irrelevant" share is small — the real question isn't data quality, it's whether **basic** and **diluted** are interchangeable for this design's purposes, which they are not (see below).

## Basic-EPS-as-fallback impact simulation (the 3 verified small-cap CIKs, real run)

`extract_eps_records()` was run twice over the same real bulk data — once with the current `EPS_TAG_PRIORITY`, once with `EarningsPerShareBasic` appended as a 3rd/4th-tier fallback — then `compute_sue()` was run on each firm's resulting series under both scenarios. No code or production tag list was changed; this uses the function's existing `tag_priority` override parameter.

| CIK | baseline quarters found | expanded quarters found | SUE computable baseline? | SUE computable expanded? | newly computable? | SUE value (unchanged) |
|---|---|---|---|---|---|---|
| 0000798081 | 13 | 13 | Yes | Yes | No | −0.573 |
| 0000723603 | 15 | 15 | Yes | Yes | No | −0.506 |
| 0000080420 | 15 | 15 | Yes | Yes | No | 1.941 |

**Newly SUE-computable if Basic EPS were added: 0.** For these 3 firms, every quarter in the window already had `EarningsPerShareDiluted` or `EarningsPerShareBasicAndDiluted` reported — Basic EPS never had a gap to fill. At n=3, this is not evidence that widening the definition is unnecessary industry-wide (the tag-distribution numbers above show ~40% of all EPS-like facts industry-wide are Basic-only, meaning *some* filers likely report Basic without Diluted in some quarters) — it is only evidence that, for the specific 3 CIKs already probed, adding Basic EPS would have changed nothing.

## Framing: does this improve measurement, or introduce a different construct?

This is the actual decision an amendment would need to resolve, not "can we extract more":

- Basic EPS and Diluted EPS are not the same measurement. Diluted EPS incorporates the dilutive effect of options, warrants, and convertible securities on the share count; Basic EPS does not. A firm with meaningful option/warrant overhang can show a materially higher Basic EPS than Diluted EPS in the same quarter.
- If Basic EPS were added as a fallback tier, the resulting SUE series for a firm (or across firms) would potentially mix quarters measured on a diluted basis with quarters measured on a basic basis, depending on which tag happened to be filed that quarter. That's a construct change to the surprise measure itself, not just a larger sample of the same construct.
- H11's pre-registration (`results/H11_PREREGISTRATION.md` §5) specifies "diluted EPS from continuing operations." Widening to include Basic EPS as a fallback would touch that definition directly.
- The evidence above supports that this is a live question worth an amendment (Basic EPS is common — 40% of industry-wide facts — and the irrelevant/other-construct share is small, so this isn't a case of chasing noise), but the 3-CIK simulation gives no evidence of urgency (zero events affected in the only real test run so far).

## What this analysis does not tell us

- Whether Basic-EPS-only quarters are concentrated in particular sectors, sizes, or filing patterns within H11's actual $50M–$2B universe — the tag distribution is industry-wide, not universe-filtered.
- How many *additional events* (not just SUE-computable firm-quarters) a wider definition would add across the full small-cap universe — only 3 CIKs were tested end-to-end.
- Whether a mixed basic/diluted series would introduce measurable bias in backtest results — that would require actually building the amendment and re-running the event study, which is explicitly gated on a decision here first.

## Next step

Per the standing workflow, this document is evidence only. Whether `amendments/H11_AMENDMENT_002.md` gets drafted to widen `EPS_TAG_PRIORITY` is your call to make from here — not a recommendation this document is making on its own.
