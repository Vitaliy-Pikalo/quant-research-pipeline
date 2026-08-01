# Research prioritization review — is H11 the highest expected-value hypothesis?

Written before H11's pre-registration is signed off, at the user's request,
specifically to try to kill H11 with a better alternative before a single
line of implementation code is written. If nothing here beats it, that's the
signal to proceed; if something does, that's the signal to pivot.

> **Outcome note, added after this review:** the conclusion below — that
> nothing here *clearly dominates* the insider-cluster hypothesis, but PEAD
> is the closest rival and wins on methodological grounds (sample size, no
> new entity mapping, pipeline fit) — led to a renumbering rather than a
> rejection. The refined PEAD test took the **H11** label and is now
> pre-registered in `results/H11_PREREGISTRATION.md`. The insider-cluster
> hypothesis, referred to as "H11" throughout the analysis below exactly as
> it was at the time this was written, is now **H12**
> (`results/H12_PREREGISTRATION.md`). Left unedited below to preserve the
> reasoning as it actually happened.

---

## 1. What survives the rigor stack, per the literature — not per intuition

Four papers anchor this section, and they don't fully agree with each other,
which is itself informative.

- **Hou, Xue & Zhang (2020, "Replicating Anomalies," *Review of Financial
  Studies*)** — the pessimistic end. Re-tested 452 published anomalies with
  value-weighted returns and NYSE breakpoints (removing microcap noise).
  **65% fail to clear even a single-test t > 1.96 hurdle. Imposing a
  multiple-testing-adjusted hurdle of t > 2.78 pushes the failure rate to
  82.1%.** Read plainly: most of the published anomaly literature does not
  survive a rigorous, corrected replication.
- **Harvey, Liu & Zhu (2016, "…and the Cross-Section of Expected Returns")**
  — proposes a t > 3.0 threshold once the full history of prior tests in the
  literature is accounted for. This is not abstract for this project —
  `stats.py`'s `harvey_liu_zhu_threshold()` already implements this exact
  correction, so whatever gets tested next will already be held to it.
- **McLean & Pontiff (2016, *Journal of Finance*)** — the mechanism paper.
  Published anomalies decay **26% out-of-sample, 58% post-publication**, on
  average. Critically for this project: **decay is significantly smaller in
  stocks with high idiosyncratic risk and low liquidity** — i.e., exactly the
  stocks large capital structurally can't arbitrage. This is the empirical
  backbone of the "capacity-constrained persistence" argument used
  throughout this project's pivot away from Beige Book.
- **Jensen, Kelly & Pedersen (2023, *Journal of Finance*, "Is There a
  Replication Crisis in Finance?")** — the optimistic counterweight. Using a
  Bayesian model across 153 characteristics in 93 countries, they find the
  **majority of factors do replicate, hold up out-of-sample, and are
  strengthened rather than weakened by joint modeling** — a materially less
  bleak read than Hou et al.

**These two camps disagree on how much of the anomaly zoo is real, but they
agree on which kind of anomaly is more likely to be real**: one with a
structural or risk-based mechanism (not purely "the market hasn't noticed
this yet"), concentrated in small, illiquid, high-idiosyncratic-risk names,
and *not* among the anomalies that have become large, liquid, commercially
packaged factors (value, size-alone, momentum-alone — all now available as
single-ticket ETFs). That is the filter applied to every candidate below.

---

## 2. Twelve candidates, including H11

Same scoring convention as this project's own `institutional_quant_research_
dossier.md` Part 2 (1–5, always oriented so **higher is better**), extended
to 8 criteria instead of 6. **Composite is an unweighted mean — read the
warning in §3 before trusting it.**

| # | Criterion | meaning |
|---|---|---|
| 1 | Econ. justification | how solid is the published mechanism/evidence |
| 2 | Persistence mechanism | structural/risk-based (durable) vs. purely informational (decays fast) |
| 3 | Capacity headroom | room to deploy retail-scale live capital without hitting the strategy's own cap |
| 4 | Implementation effort | 5 = easy/fast, 1 = heavy build |
| 5 | Data availability | 5 = clean and free, 1 = effectively paid-blocked |
| 6 | Pipeline compatibility | 5 = near drop-in to `cv.py`/`stats.py`/`feature_store.py`/`costs.py` |
| 7 | Novelty | 5 = fresh angle, 1 = textbook-famous |
| 8 | Arbitrage resistance | 5 = unlikely already priced away, 1 = fully institutionalized |

| Hypothesis | Econ | Persist | Capacity | Effort | Data | Compat | Novelty | ArbRes | **Composite** |
|---|---|---|---|---|---|---|---|---|---|
| **H11 — small-cap insider clusters** | 4 | 4 | 3 | 2 | 4 | 4 | 3 | 3 | **3.38** |
| PEAD, small/micro-cap tail, price-based surprise (no consensus data) | 5 | 4 | 4 | 4 | 5 | 5 | 1 | 2 | **3.75** |
| Board-interlock / director-network info diffusion | 2 | 3 | 3 | 1 | 4 | 3 | 5 | 5 | **3.25** |
| Patent-citation centrality (USPTO PatentsView) | 3 | 3 | 4 | 2 | 4 | 3 | 4 | 3 | **3.25** |
| Generic price momentum (12-1) — *benchmark, not a real candidate* | 5 | 3 | 2 | 5 | 5 | 5 | 1 | 1 | **3.38** |
| Search/attention (Wikipedia pageviews) | 2 | 2 | 3 | 5 | 5 | 4 | 1 | 2 | **3.00** |
| Merger-arbitrage deal-spread premium | 4 | 3 | 4 | 2 | 3 | 3 | 2 | 2 | **2.88** |
| Crypto funding-rate/basis carry | 3 | 2 | 4 | 3 | 4 | 2 | 2 | 2 | **2.75** |
| Options dealer-gamma / opex pinning | 4 | 4 | 3 | 2 | 1 | 2 | 3 | 3 | **2.75** |
| Earnings-call tone via LLM | 3 | 2 | 3 | 3 | 2 | 3 | 2 | 2 | **2.50** |
| Short interest (FINRA bi-monthly) | 3 | 2 | 2 | 3 | 3 | 4 | 2 | 2 | **2.63** |
| Index reconstitution price pressure | 2 | 1 | 3 | 4 | 3 | 4 | 1 | 1 | **2.38** |

Beige Book (H10/H10b), 13F copycat (H8), and FX carry (H9) are excluded —
already tested, already null, not re-litigated here.

---

## 3. Why the composite score cannot be trusted on its own

This project's own dossier already flagged this failure mode for H14
(environmental/mood anomalies): a high composite can appear precisely
*because* an idea is so dead that nobody bothers competing for it, which
makes every "cost" column look favorable while Expected Alpha is actually
near zero. **Generic momentum scores a 3.38 here — tied with H11** — for
exactly that reason inverted: its economic justification is excellent
*in the literature*, but it is so thoroughly institutionalized (single-ticket
ETFs exist) that essentially none of that documented return is available to
a new entrant. A composite score cannot see that; only reading Persistence,
Capacity, and Arbitrage-Resistance *together* against Econ. Justification
can. **Momentum is included specifically as a warning label on this table,
not as a real candidate.**

Applying that same lens narrows the real contest to four: **H11, PEAD
(small-cap tail), board-interlock, and patent-citation centrality** — the
only candidates with Arbitrage-Resistance ≥ 3 *and* Economic Justification
≥ 2. Options gamma has the best mechanism on the whole list (Persistence 4,
tied for highest) but is disqualified in practice by Data = 1 — this
project's $0 budget cannot get free historical options history, full stop,
independent of how good the theory is.

### Head-to-head: H11 vs. its closest real rival, PEAD

PEAD restricted to the small/micro-cap, low-analyst-coverage tail, using the
earnings-announcement-window abnormal return itself as the surprise measure
(no analyst-consensus data needed — this removes the "consensus estimate
gap" the project's own `zero_budget_priority_ranking.md` flagged against
H2), is the one candidate that beats H11 on raw composite. It should be
taken seriously, not waved off:

- **Evidence base is deeper.** PEAD is one of the most replicated results in
  finance, surviving in some form across essentially every major replication
  study cited in §1, including the pessimistic Hou-Xue-Zhang read.
- **Lower implementation risk.** No sixth hand-built ticker/CIK mapping is
  needed — the failure mode that has bitten this project in four of its five
  prior mappings (13F CUSIP, H10's district map, H10b's FDIC map, and now
  H11's Form-4-to-issuer map). PEAD needs only 8-K Item 2.02 timestamps
  (already free EDGAR data) joined to the existing price panel.
- **Likely a much larger event count**, which matters directly for the power
  problem H11's own §13 flags: every small-cap files a quarterly earnings
  release, meaning thousands of candidate events across the sample vs. H11's
  comparatively rare 3-insider clusters. More events at a given effect size
  means a cleaner statistical read, faster.

But it is **not a clean win**, and should not be oversold as one:

- **Novelty is the lowest score on this whole table (1/5).** It is taught in
  every asset-pricing course and has been systematically harvested for
  decades.
- **The net-of-cost question is genuinely disputed, not settled.** Chordia,
  Goyal, Sadka, Sadka & Shivakumar (2009) find transaction costs consume
  **70–100% of PEAD's paper profits**, concentrated exactly where the raw
  effect is largest — illiquid stocks (0.04%/month for the most liquid
  quintile vs. 2.43%/month for the least liquid). Other studies (Battalio &
  Mendenhall 2011; Li 2016) find it survives costs. This is the identical
  "real, but is it tradeable at live cost assumptions" question H11 already
  has to answer in its own §10 — PEAD does not sidestep it, it just moves
  the same uncertainty to a better-documented anomaly.

**Neither candidate clearly dominates the other.** PEAD wins on evidence
depth, implementation safety, and expected event count. H11 wins on novelty
and has a more specific, less-picked-over capacity-constraint story (a
handful of insiders acting in concert is a narrower, less commercially
packaged signal than "buy stocks that beat earnings," which off-the-shelf
"earnings momentum" ETFs already exist for).

Board-interlock and patent-citation centrality both score competitively on
novelty and arbitrage-resistance, but for the opposite reason PEAD is
attractive: their literature anchor is thin. Board-interlock's justification
leans on adjacent social-network-in-finance work (Cohen-Frazzini-Malloy-style
"connections" papers) rather than a direct, established insider-cluster-style
result, and patent-citation centrality's return-predictability literature
(Kogan-Papanikolaou-Seru-Stoffman) is real but narrower and more indirect
than the insider-trading or PEAD literatures. High novelty here is partly
*because* these are unproven, not because they're validated-but-overlooked —
a materially different, riskier kind of "high score" than PEAD's or H11's.

---

## 4. Why this probably won't work — the case against H11, argued to win

This is the same design already documented in `H11_PREREGISTRATION.md`
§16–17, restated here without the hedging, as requested.

**The reversal confound is not a footnote, it may be the whole result.** The
2025 microcap paper cited in the pre-registration found cluster-buy returns
concentrated in stocks that had already dropped >10%. A 6-month momentum
tercile control does not cleanly remove a 20-day reversal effect — a stock
can be flat over six months and still down 15% in the last three weeks. If
the honest result of this design is "insiders are decent at timing dips,
which is itself a version of a known value/reversal anomaly," that is not
what the hypothesis in §2 of the pre-registration claims, and the design as
currently specified may not be able to fully tell the two apart.

**Retail crowding has a multi-year head start.** This project's entire pivot
away from Beige Book rests on the argument that institutionally-published
signals are dead on arrival. Insider-cluster screeners (2iq, InsiderArbitrage,
OpenInsider, Quiver Quant) have been commercially selling this exact signal
to retail and small funds for years. The capacity-constraint argument
explains why *large* funds ignore it; it says nothing about whether the pool
of capital this design is actually competing against — other small, nimble,
retail-adjacent traders using the same public screeners — has already
compressed the historical academic effect size. There is no way to measure
this before running the backtest, only after, which means a positive result
here carries more uncertainty about its true forward value than the
statistics alone will show.

**The routine/opportunistic filter is an estimated label, not ground truth.**
An insider with genuinely irregular trading history that happens to fall in
the same calendar window as colleagues could be misclassified as routine and
silently excluded, or the reverse. This isn't a hypothetical edge case — it's
inherited directly from Cohen-Malloy-Pomorski's own methodology, and this
project has no independent way to validate the classification against
ground truth (nobody discloses whether a given trade was "opportunistic").

**The mapping problem has a 4-for-5 failure rate in this project, not 0-for-5.**
Every one of the four prior hand-built entity mappings (13F CUSIP, H10's Fed
district map, H10b's FDIC-to-ticker map) contained at least one real,
consequential error, each caught only by an automated gate. There is no
principled reason to expect the fifth — Form 4 issuer CIK to price-panel
ticker — to be the first one that's clean on the first pass.

**The power problem is real and might simply end the test before it starts.**
Three-or-more-distinct-insider, opportunistic-only, non-earnings-window
clusters in a $50M–$2B universe are a genuinely narrow filter stacked on top
of a genuinely narrow filter. The pre-registration's own §13 power check
exists because there's a real chance the qualifying event count comes in
too low to say anything at all — and if it does, that isn't a fixable bug,
it's the universe telling you the question can't be answered on $0-budget
data in this cap range.

**The base rate in this specific project is 0 for 4.** Every hypothesis
tested so far — FX carry, 13F copycat, Beige Book, Beige Book relocalized —
came back null. That is not evidence H11 will also fail; each null had a
distinct, well-understood cause. But a track record of 0/4 is itself
Bayesian information, and a pre-registration this thorough should not be
read as if rigor of process implies a higher chance of a positive result.
It doesn't. It only implies that whatever the result is, it can be trusted.

**The 50bps small-cap cost assumption is asserted, not verified against this
project's own data.** Unlike the 20bps regional-bank assumption, which
survived contact with H8/H10's actual returns, this number has not yet been
checked against real small-cap bid-ask spread data. If real spreads in the
$50M–$500M tail of this universe run wider than 50bps — plausible, given
how illiquid the bottom of that band can get — §10's decision rule could
fail on cost grounds alone, independent of whether the raw effect is real.

---

## 5. Verdict

**Nothing on this list clearly dominates H11.** PEAD (small/micro-cap tail)
is the one real rival, and it wins on evidence depth, implementation safety,
and likely statistical power — but it loses on novelty and arrives with its
own unresolved, decades-old dispute about whether it survives transaction
costs at all (§3). That is a genuine trade-off, not a knockout.

Given the user's own decision rule — pivot only if something *clearly*
dominates — **the honest answer is that this does not clear that bar in
either direction.** Recommendation, stated plainly rather than hedged:

- **Do not discard H11.** Its pre-registration is done, its mechanism is
  distinct from anything already tested, and it remains defensible.
- **Sequence PEAD (small/micro-cap tail) ahead of it anyway**, for a
  cost/reward reason rather than a "better hypothesis" reason: it is cheaper
  to fail fast on. No new hand-built mapping, likely an order of magnitude
  more events (side-stepping H11's own power-check risk before spending a
  trial finding out), and a deeper evidence base to interpret the result
  against. If PEAD also comes back null, that is a strong, cheaply-bought
  data point about how much edge is really left in free-data anomalies at
  all — worth knowing before committing to H11's heavier build.
- **If PEAD is supported**, H11 is still worth running afterward — they test
  different mechanisms (behavioral underreaction to public news vs.
  informed-insider signaling) and a portfolio combining both, or even an
  interaction test (do insider clusters predict returns *beyond* the earnings
  surprise they may be reacting to), becomes a legitimately novel follow-on
  hypothesis with its own trial count — not proposed as part of this review,
  flagged only because it falls out naturally of running both.

This changes the immediate next step, not the destination: pre-register PEAD
(small/micro-cap tail) next, run it first, keep `H11_PREREGISTRATION.md`
signed off and queued right behind it.
