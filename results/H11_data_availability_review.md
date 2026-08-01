# H11 data availability review — feasibility gate before implementation

Written before `H11_PREREGISTRATION.md` is frozen, per the user's request, to
answer five specific questions before any data is collected. **Important
caveat up front: this project's Claude sandbox cannot reach `sec.gov` or
`data.sec.gov`** (confirmed by testing during this review — only
`pypi.org` and `github.com` resolve), the same constraint recorded in
earlier handoffs. Everything below is therefore a **desk review** grounded
in SEC's own published rules, timelines, and documented data-quality
literature — not a live pull. Every quantitative estimate in §4 needs
confirming with an actual local count before it's trusted. A small
verification script is proposed at the end for exactly that purpose,
following this project's standing workflow (Claude writes the script, the
user runs it, Claude reads the output).

---

## 1. Can point-in-time XBRL be reliably obtained for the full 2015–2025 sample?

**Yes, on coverage; with one real, documented quality caveat.**

The SEC's XBRL mandate reached full coverage — including smaller reporting
companies, the population this design lives in — for fiscal periods ending
on or after **June 15, 2011**. The 2015–2025 sample window sits entirely
inside the fully-mandated era; there is no coverage cliff or phase-in edge
to worry about, unlike a sample that started earlier.

The real caveat is **tagging quality, not availability**. Companies can tag
a given financial-statement line item with a standardized `us-gaap` element
(e.g. `EarningsPerShareDiluted`) or with a firm-specific **custom extension**
element. The academic XBRL data-quality literature consistently finds that
**higher custom-tag usage correlates with lower financial-reporting quality
and is more common among exactly the kind of filer this design's universe
selects for** (smaller, less-covered companies) — the tagging-quality risk
is not evenly distributed, it's concentrated where this study is aimed.
This does not block the study; it means a **fallback tag-priority list**
(not a single hardcoded tag name) is required, and its hit rate needs to be
measured and reported, not assumed. This was already anticipated in
§13.1 of the pre-registration (the as-filed audit); it now gets a second,
explicit companion check (§4 below, and the amendment in §6).

**Practical sourcing note, uncovered during this review and worth folding
in:** the pre-registration's §15 describes pulling XBRL via the per-CIK
`companyfacts` endpoint. The SEC also publishes **Financial Statement Data
Sets** — quarterly bulk CSV archives (`num.txt`/`sub.txt`/etc.), free,
official, no key, covering every XBRL filer for that quarter in one
download. For a study spanning ~40 quarters across the full small/micro-cap
universe, this bulk path is far more robust than ~2,000+ individual per-CIK
API calls (fewer points of failure, no per-company rate-limit exposure, and
it's the same underlying data). Recommended as the **primary** source, with
per-CIK `companyfacts` calls reserved for the audit spot-checks in
pre-registration §13.

---

## 2. Can 8-K Item 2.02 timestamps be reconstructed without look-ahead bias?

**Yes — this is the one part of the design with the least residual risk.**

EDGAR assigns every filing, including furnished (not just filed) items, an
immutable **accession number and timestamp** at the moment of submission.
Item 2.02 earnings releases are typically *furnished* under Item 2.02 (and
often Item 9.01 for the exhibit) rather than *filed* — a liability
distinction under Exchange Act Rule 12b-20/Item 2.02's own adopting release,
not a timestamping one. Furnished items get the same accession-time
treatment as filed ones. This is the identical mechanism this project has
already relied on correctly in every prior hypothesis (H8's 13F timestamps,
H10/H10b's Beige Book release dates), so there's no new category of
look-ahead risk being introduced, only a new document type.

Two real edge cases, both handleable in code, neither a blocker:

- **8-K/A amendments.** An amendment must never be used as the event
  timestamp in place of the original filing — only the *original* 8-K's
  accession time counts as `known_at`, unless the original omitted Item 2.02
  entirely and the amendment is the first filing to add it (rare, but must
  be checked for, not assumed away).
- **No 8-K Item 2.02 at all.** Some smaller filers skip a standalone
  earnings 8-K and let the 10-Q/10-K itself be the first public disclosure.
  This is exactly why §4.2 of the pre-registration already has a fallback
  rule and §13.4 already requires reporting the fallback rate — this review
  confirms that requirement is necessary, not optional, given how real this
  edge case is expected to be in a small-cap-only universe.

---

## 3. Coverage gaps, format changes, taxonomy changes, and SEC edge cases

| issue | real? | how it's handled |
|---|---|---|
| Custom-tag EPS fragmentation (§1) | yes, documented, concentrated in this design's target universe | fallback tag-priority list + measured hit rate, folded into §13 |
| ASC 606 revenue-recognition standard adoption (~2018) changed how revenue-related XBRL tags are structured | yes, well documented as a structural break in *revenue* tagging | does not directly affect diluted EPS as a bottom-line figure, but the transition period (fiscal 2018 for most calendar-year filers) is flagged as a specific date range to spot-check in the as-filed audit, since a company mid-transition could tag inconsistently across quarters |
| COVID-19 filing-deadline relief (SEC conditional relief orders, March 2020) | yes, a real, dateable SEC policy action | some 2020 filings were delayed beyond their normal calendar slot; this can create irregular gaps in the "5 consecutive quarters" history requirement (§3) for firms that used the relief. Handled by treating "consecutive" as consecutive *fiscal* quarters, not consecutive *calendar* quarters, so a genuinely late-but-not-skipped filing doesn't wrongly disqualify a firm |
| Ticker symbol reuse/changes over a 10-year window | yes — **this project has already been burned by exactly this** (H10's recycled BRKL ticker) | the highest-risk item in this whole review; addressed directly in §5 |
| Dual-class share structures (multiple share classes, each separately tagged) | yes, a known real edge case, more common than expected even outside mega-caps | requires summing shares-outstanding tags across classes for a correct market-cap figure; auditable, not a blocker |
| us-gaap taxonomy revised annually by FASB/XBRL US | yes in general, but the specific EPS concepts used here (`EarningsPerShareDiluted`, `EarningsPerShareBasic`) are core, stable identifiers that have not been part of the more volatile taxonomy churn (which concentrates in newer/niche disclosure areas) | low incremental risk beyond the custom-tag issue already flagged |
| EDGAR full-text search / structured data coverage window | full electronic-filing coverage since 2001 | no gap relative to the 2015–2025 sample |

**No item in this table is a fundamental limitation.** All are documented,
known failure modes with a concrete handling rule — which is a materially
different finding than H10's release-date and boilerplate-contamination
bugs were, both of which were *undocumented* traps this project found the
hard way. Nothing here is expected to be a surprise of that kind, but §13's
audits exist specifically because "documented in the literature" and
"actually handled correctly in this implementation" are not the same claim
until verified.

---

## 4. Estimated final usable event count

**Desk estimate, not a verified count — treat as an order-of-magnitude
sanity check, not a number to build the power analysis on.**

- Jay Ritter's widely-cited listed-firms dataset puts total U.S. domestic
  operating companies on major exchanges at **3,657** (end of 2025). The
  $50M–$2B small/micro-cap band is plausibly the largest single tier of
  that population — small-cap alone (roughly $300M–$2B) and micro-cap
  (roughly $50M–$300M) combined likely cover **on the order of 2,000–2,500
  companies** at any point in time, allowing for the usual churn (IPOs,
  delistings, cap appreciation moving firms in and out of the band).
- At 4 quarterly events per firm-year, a **static** cross-section would
  imply roughly 2,000–2,500 × 4 × 11 years ≈ **90,000–110,000** firm-quarter
  slots before any filter. The universe is not static (§3 of the
  pre-registration re-evaluates it per event), which pulls the true count
  down from that ceiling but also captures firms that only spent part of
  the sample in-band, which the static estimate misses — the two effects
  partially offset.
- Applying the §3 XBRL-history requirement (≥5 consecutive quarters,
  excludes each firm's first year), the §8 M&A-window exclusion, and an
  allowance for the custom-tag/fallback losses in §1 and §3, a reasonable
  **conservative planning range is 30,000–60,000 usable firm-quarter
  events** over the full sample — the exact figure is exactly what §13.3's
  power check is for, and this range is offered only to confirm there is no
  plausible path to an underpowered sample.

**This is 100–400x larger than H12's own pre-data estimate of 150–250
qualifying insider-cluster events.** That gap is the concrete, numeric
version of the sequencing argument in `H11_prioritization_review.md` — it
isn't just that PEAD is cheaper to build, it's that the sample-size safety
margin is enormous by comparison, even under conservative assumptions.

---

## 5. Every manual or hand-curated step, ranked by risk

The user's specific ask — minimize subtle-error opportunities — deserves a
distinction this project's own history supports: a **hand-built entity
mapping** (subjective judgment calls, the category that has produced a real
bug in 4 of this project's prior 4 attempts: 13F CUSIP, H10's Fed district
map, H10b's FDIC map) is a fundamentally different risk than a
**deterministic, code-enforced decision rule** (same rule applied uniformly
to every record, auditable in one pass, no per-case judgment). This design
has exactly one of the first kind and several of the second.

| step | kind | risk | mitigation |
|---|---|---|---|
| **CIK ↔ price-panel ticker, point-in-time** | hand-built mapping | **highest** — SEC's own `company_tickers.json` gives only the *current* ticker per CIK, not the ticker *at a past date*; a company that changed or had its ticker reused (this project's own BRKL precedent) needs point-in-time resolution, which the official file doesn't fully provide on its own | join on CIK, not ticker, wherever possible; where ticker is unavoidable (matching to the existing price panel), cross-check against company name and SIC-implied industry at each point in time, and apply the same minimum-observations gate that caught BRKL in H10 |
| EPS tag-priority fallback list | deterministic rule | moderate | fixed, published list of tag names in priority order, applied identically to every filer; hit rate and fallback rate reported, not assumed (§13.1 amendment, §6 below) |
| 8-K Item 2.02 vs. 10-Q/10-K fallback assignment | deterministic rule | moderate | already required to be reported by §13.4 of the pre-registration |
| Dual-class share aggregation for market cap | deterministic rule | low-moderate | sum all reported share-class tags for a CIK at each date; audited on a sample of known dual-class small caps |
| SIC sector code | direct field, no mapping | low | pulled straight from EDGAR's own submissions record, no judgment involved |

Only the first item is genuinely comparable in kind to this project's prior
mapping failures. Everything else is a rule, not a judgment call, which is
the safer category by this project's own track record.

---

## 6. Verdict and recommended amendment

**No fundamental limitation found.** Coverage is real and mandated for the
full sample window, timestamps are point-in-time safe by construction, and
the event-count margin over H12 is large even under conservative
assumptions. This clears the gate.

**Two non-fundamental refinements are worth folding into the
pre-registration before freezing, since both were surfaced by this review
and neither changes the hypothesis or the decision rule:**

1. Declare the **SEC Financial Statement Data Sets** (bulk quarterly, §1) as
   the primary data source, with per-CIK `companyfacts` reserved for audits.
2. Add an explicit, numeric reporting requirement for the **custom-tag
   fallback rate** (§1/§3), alongside the already-required 8-K-fallback rate
   (§13.4) — both get reported as a data-quality table before any return is
   interpreted, same standard as H10b's locality-weight audit.

Both are applied directly to `H11_PREREGISTRATION.md` below, before
freezing, rather than deferred to a post-hoc amendment — consistent with the
instruction that a review finding gets folded in now if it changes
anything material.

---

## Verification script to run locally (proposed, not yet written)

Before committing to full implementation, a single small script —
`backtests/h11_data_probe.py` — should: pull the SEC Financial Statement
Data Sets for 2–3 sample quarters, join against a small known set of
small-cap CIKs, and report (a) what fraction resolve via the standard EPS
tag vs. a fallback, (b) what fraction have a qualifying 8-K Item 2.02 within
5 days of their 10-Q vs. requiring the 10-Q fallback, and (c) a rough count
of qualifying firm-quarters in that sample window. This directly tests §4's
estimate and §13's two audits at small scale, cheaply, before committing to
pulling the full 2015–2025 panel. Proposed as the actual first implementation
step once the pre-registration is signed off — not written yet, per the
"no code before commit" instruction.
