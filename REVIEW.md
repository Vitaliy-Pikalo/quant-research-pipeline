# REVIEW.md -- Milestone: SEC request telemetry + XBRL tag diagnostics (instrumentation)

Per the standing workflow: this is the handoff document for external
(GitHub-based) review of this milestone. Supersedes the prior milestone's
`REVIEW.md` (preserved in git history at `7b2e94b`'s predecessor commits).

**Scope note, stated up front, same as last milestone:** this is
instrumentation, not a heuristic or filter change. `custom_tag_fallback_rate()`
and `extract_eps_records()` are byte-for-byte unchanged. Every `fetch_*`
function's request/response/exception behavior is unchanged -- `telemetry`
is an additive, defaulted-to-None parameter throughout.

## What changed

Directly in response to the first real probe run's findings (3 CIKs,
2022q2/q3): a clean run with 0 crashes but no way to tell whether SEC
access was actually healthy, a 52.3% custom-tag fallback rate with no way
to inspect which tags drove it, and a misleadingly-labeled "8-K Item 2.02
filings found" metric that was actually each CIK's entire historical count.

- **`data_connectors/telemetry.py`** (new) -- `RequestRecord`,
  `RequestTelemetryCollector`, `instrumented_get()`. Every `fetch_*`
  function across all three connectors now accepts an optional `telemetry`
  parameter; when supplied, exactly one record is captured per request
  (endpoint, HTTP status, response size, timestamp, elapsed time, any
  rate-limit headers SEC sends) -- including the real status code on a
  4xx/5xx response, captured before `raise_for_status()` raises on it, not
  skipped because the request ultimately failed. `retry_count` exists but
  is always 0 -- no retry logic exists anywhere in this project yet; the
  field is there so a future retry implementation has somewhere to report
  to without a second instrumentation pass. 16 unit tests against a fake
  session/response, no network.

- **`data_connectors/sec_financial_statement_datasets.py`**:
  `tag_distribution_diagnostics()` (new) -- top EPS-like tags with
  count/namespace/accepted-or-rejected, up to 10 examples of tags
  classified as custom, and a **second, independent** custom-tag rate
  computed from the `version` column's taxonomy namespace (`us-gaap` etc.)
  rather than tag-name string matching, reported alongside the existing
  rate for direct comparison. `fetch_quarter()` now threads `telemetry`
  through. 11 new unit tests.

- **`data_connectors/sec_company_tickers.py`, `sec_8k_item202.py`**:
  `fetch_submission()`, `fetch_company_tickers()`, `fetch_item_202_filings()`
  now thread `telemetry` through via `instrumented_get()`. `sec_8k_item202.py`'s
  `fetch_item_202_filings()` docstring now explicitly notes it hits the
  identical `sec_submissions` endpoint as `fetch_submission()` -- previously
  an implicit fact, now visible directly in any run's telemetry summary as
  two same-endpoint requests per attempted CIK.

- **`hypotheses/h11_pead/probe_report.py`**: `eightk_item202_filings_found`
  renamed to `historical_item202_filings_retrieved` (field, markdown label,
  and JSON key) with an explicit note added to `STANDARD_NOTES` explaining
  the metric is each CIK's all-time count, not scoped to the requested
  quarters -- the exact wording-clarity fix requested. Two new report
  sections: **SEC connectivity** (from a `RequestTelemetryCollector.summary()`)
  and **XBRL tag diagnostics** (from `tag_distribution_diagnostics()`), both
  rendering an explicit "not captured for this run" statement rather than
  silently omitting the section when the corresponding data isn't supplied.
  Full per-request detail goes to `report.json` only (`sec_request_records`),
  keeping the markdown summary readable. 10 tests (4 new).

- **`backtests/h11_data_probe.py`**: creates one `RequestTelemetryCollector`
  shared across every SEC request the run makes (identifiers, 8-K lookups,
  FSDS quarter pull), and calls `tag_distribution_diagnostics()` on the
  bulk `num_all` alongside the existing `custom_tag_fallback_rate()` call.
  Both flow into `build_probe_report()`. 7 end-to-end dry-run tests (2 new),
  now asserting telemetry and tag diagnostics actually populate through the
  real orchestrator, not just through `build_probe_report()` called directly.

- **Bundled in, not a separate change**: the `SEC_USER_AGENT` fix from
  earlier this session (`"Vitaliy Pikalo pikalo.vitaliy@gmail.com"`
  replacing the `example.com` placeholder) lands in these same connector
  files' commits, since it was still uncommitted.

**155 -> 179 -> 210 tests pass** across the last three milestones; this one
adds 31 (16 telemetry + 11 tag diagnostics + 4 probe-report rendering).

## Why it changed

Directly per the instrumentation milestone approved after reviewing the
first real probe: "the remaining issues are mostly observability gaps, not
evidence the pipeline is wrong" -- this milestone closes exactly those gaps
(connectivity visibility, tag-rate inspectability, metric-label clarity)
without touching the extraction rule or the tag-priority list, per explicit
instruction not to change heuristics until the distribution is understood.

## New assumptions introduced

- `_STANDARD_TAXONOMY_PREFIXES` (`us-gaap`, `dei`, `srt`, `country`,
  `currency`, `invest`, `stpr`, `naics`, `sic`, `exch`) is used to compute
  the namespace-based custom-tag rate. This list is XBRL US's commonly-cited
  standard/shared taxonomies but has not been cross-checked against SEC's
  complete, authoritative list of every taxonomy it ever accepts -- if a
  legitimate standard taxonomy is missing from this set, the namespace-based
  rate would slightly overstate "custom." This is exactly the kind of thing
  the next real probe run (with `top_tags` visible) should surface if it's
  a material issue.
- SEC's rate-limit header names (`Retry-After`, `X-RateLimit-Limit`,
  `X-RateLimit-Remaining`, `X-RateLimit-Reset`) are assumed opportunistically
  -- SEC does not formally document sending any of these. If none ever
  appear, `any_rate_limit_headers_observed` will simply always read `False`,
  which is itself informative (either SEC never signals limits this way, or
  this project has never come close to triggering one).

## New invariants introduced

None. This is instrumentation over existing behavior, not a new rule.

## Validation performed

- **210 tests pass** (`python -m pytest tests/`), all in this milestone
  synthetic/fixture-based, no network.
- `instrumented_get()` is tested for behavior-preservation specifically
  (same return value, same exceptions, same headers/timeout passed through)
  independent of whether `telemetry` is supplied -- the point being that
  wiring this into three connectors could not have silently changed what
  they do.
- `tag_distribution_diagnostics()`'s namespace-based rate is tested against
  a case specifically constructed to diverge from the tag-name-based rate
  (a standard `EarningsPerShareBasic` us-gaap tag outside `EPS_TAG_PRIORITY`)
  -- confirming the hypothesis raised in the last review (that the 52.3%
  finding might be partly a heuristic artifact) is at least mechanically
  real, not confirming it's the actual explanation for the live number,
  which only a real run's `top_tags` output can settle.
- The end-to-end dry run (`test_h11_data_probe_e2e.py`) was extended to
  confirm telemetry and tag diagnostics actually flow through the real
  `probe()` orchestrator end to end (7 requests recorded across 3 CIKs x 2
  submissions calls + 1 FSDS pull, matching the now-visible duplicate-
  endpoint pattern), not just that `build_probe_report()` can render them
  when handed pre-built inputs directly.

## Remaining risks

Carried forward, unchanged by this milestone (instrumentation doesn't fix
any of these, it makes them measurable):

1. 8-K/A amendment fallback (original omits Item 2.02, amendment adds it)
   still not implemented.
2. The 8-K JSON-shape assumption is still unverified against live data.
3. CIK -> ticker resolution in the probe is still current-ticker-only, not
   point-in-time.

New, from this milestone:

4. **`_STANDARD_TAXONOMY_PREFIXES` completeness is unverified** (see New
   assumptions) -- low risk, self-correcting once real `top_tags` data is
   inspected.
5. **The duplicate-submissions-endpoint-per-CIK pattern is now visible but
   not fixed** -- deliberately, per this milestone's instrumentation-only
   scope. Worth folding into the data-layer design (see Architectural note
   below) rather than patched ad hoc in the probe script.
6. **Whether the 52.3% custom-tag rate is real or a heuristic artifact is
   still unresolved** -- this milestone built the instrument to answer that
   question; it has not yet been pointed at real data with enough history
   to answer it. That's the next probe run's job.

## Architectural note, captured for the full-panel design (not implemented this milestone)

The first probe run's low event count (1 of 3) traced to a structural
issue: the SUE calculation needs up to 8 quarters of trailing EPS history,
but a probe invoked with only 2 requested quarters can only supply
whatever comparative-period facts happen to be tagged inside filings
submitted in that narrow window. This is a data-layer design question, not
a bug, and the intended shape for the eventual full-panel build has been
specified (not built) as:

```
SEC historical facts
        |
        v
point-in-time financial fact store
        |
        v
event generator requests required history window
        |
        v
SUE calculation
        |
        v
event-study framework
```

The event generator should request the history it needs; the data layer
should accumulate and serve it. This milestone deliberately does NOT
implement that fact store -- `backtests/h11_data_probe.py` still requests
whatever quarters are passed on the command line and works with whatever
history happens to land inside them, which is fine for a probe whose job is
proving connectivity and extraction correctness, but is explicitly NOT the
production design. Building the fact store is its own engineering decision,
warranting its own design spec (matching this project's standing practice
of writing a spec before a structural change), and should happen only
after the wider-window probe (this milestone's next step) confirms the
8-quarter requirement is well understood empirically, not before.

## Specific areas where external review should focus

1. **`instrumented_get()`'s error-path telemetry recording**
   (`data_connectors/telemetry.py`) -- confirm a 4xx/5xx response is always
   captured with its real status code before `raise_for_status()` raises,
   under every call site, not just the tested ones.
2. **The namespace-based vs. tag-name-based custom-tag rate comparison** --
   whether `_STANDARD_TAXONOMY_PREFIXES` is the right list, and whether the
   `rates_agree_within_5pct` threshold is a reasonable bar for "these two
   measurements are telling the same story."
3. **The duplicate-submissions-request pattern** (Remaining risks item 5) --
   whether this is worth fixing now (a small dedupe-by-CIK cache) or
   properly folded into the future fact-store design instead.
4. **Whether the architectural note above is scoped correctly** -- this
   milestone treats the point-in-time fact store as future work requiring
   its own spec; worth confirming that sequencing (wider probe first, fact
   store design second) rather than jumping straight to the fact store now.
