# H11 rationale — why this PEAD replication is worth doing

Written before the pre-registration, answering one question directly, as
requested: **decades of post-earnings-announcement-drift literature already
exist — why spend a trial on it again?**

## The answer that would NOT be sufficient, stated first

"Because PEAD is a well-established anomaly, it's probably real, so testing
it is worthwhile" is not the justification used here, and would not clear
this project's own bar. §1 of `H11_prioritization_review.md` already showed
that "well-established" and "still has edge for a new entrant" are different
claims — generic momentum is exactly as well-established as PEAD and scored
among the *worst* candidates reviewed, precisely because it's now fully
institutionalized (single-ticket ETFs exist). Familiarity in the literature
is not the reason to run this.

## The actual reasons

**1. The load-bearing literature's samples mostly predate the market this
project would actually trade in.** Bernard & Thomas (1989, 1990), Chan-
Jegadeesh-Lakonishok (1996), and even Chordia-Goyal-Sadka-Sadka-Shivakumar
(2009) draw on samples ending well before 2010. XBRL-tagged, machine-
readable financial statements have only been mandatory for all filers since
2009, zero-commission retail trading is a post-2019 phenomenon, and
McLean & Pontiff (2016) establish that anomalies decay over time as they
become known. Whether PEAD survives with modern point-in-time discipline in
a **2015–2025** sample — after a decade of exactly the kind of market-
structure change that should erode it, if anything does — is a live
question, not a settled one. This is the "least-studied segment" angle
applied to *time*, not just market cap.

**2. This design closes a point-in-time gap most of the literature doesn't
bother with.** Two specific improvements over standard practice:
- **As-filed, not restated, earnings.** Most PEAD studies (and virtually all
  retail backtests) pull a "clean" historical EPS series from a data vendor.
  That series is typically the *most recently restated* value, not what was
  actually reported at the time — a company that later restates a quarter's
  earnings changes that quarter's historical value in the vendor's database,
  which silently reintroduces look-ahead bias into any "surprise" measure
  computed from it. Pulling EPS from each individual 10-Q/10-K's own XBRL
  instance document, as originally filed, avoids this by construction.
- **Timestamp-, not date-, precision on the announcement itself.** Using the
  SEC's 8-K Item 2.02 accession timestamp (to the second, machine-readable,
  free from `data.sec.gov`) rather than a calendar date lets the design
  correctly determine same-day-close vs. next-day-close entry based on
  whether the release happened before or after market close — the exact
  `known_at` discipline `feature_store.py` already enforces, applied here to
  a data source precise enough to actually use it.

**3. This design is built specifically to adjudicate a real, unresolved
dispute in the literature, not to assume an answer.** Chordia et al. (2009)
find transaction costs consume 70–100% of PEAD's paper profits, concentrated
in the most illiquid names — where the raw effect is also largest.
Battalio & Mendenhall (2011) and Li (2016) find it survives costs. Both
sides are testing the same anomaly against a single flat cost assumption;
they disagree because they picked different ones. This design instead
reports net returns across a **continuous liquidity spectrum** (§6 of the
pre-registration) rather than picking one bps number and one cap-size cutoff
— which segment, if any, survives realistic costs becomes a direct empirical
output of this test rather than an assumption fed into it. That is a
genuine methodological contribution: turning a fought-over assumption into a
measured result.

**4. This project's rigor stack is not what most of the literature applies.**
Purged/embargoed cross-validation, a deflated Sharpe ratio checked against
this project's own **running cumulative trial count** (currently 78, soon
82+), Benjamini-Hochberg FDR across the full test list, and block-bootstrap
inference for overlapping event windows are standard in this codebase and
close to absent from the classical PEAD literature, which mostly relies on
calendar-time portfolio sorts and Fama-MacBeth regressions. Whether PEAD
clears *this* bar, specifically, hasn't been answered by any of the papers
cited above.

**5. It is a cheap, fast calibration test with real decision value, not just
scientific value.** Four hypotheses in, zero supported. Before spending the
Form-4-ingestion and entity-resolution effort H12 requires, running the
methodologically cheapest, best-evidenced, easiest-to-implement candidate
first answers a higher-order question: **is there any free-data equity
anomaly left that survives this project's specific evaluation framework at
all?** A positive result here is informative about *this project's own
validation stack*, not just about PEAD. A null result is equally informative
— and cheaply bought, at a fraction of H12's engineering cost.

## What a positive vs. negative result would each mean

- **Supported** (§10 decision rule, in the pre-registration, cleared): real
  evidence that at least one free-data equity anomaly survives purged CV,
  cumulative-trial-count deflated Sharpe, and realistic liquidity-scaled
  costs in a modern sample. Directly informative for whether to invest in
  H12's heavier build, and for how much confidence to place in this
  project's methodology going forward.
- **Not supported**: not a wasted trial. Given how much cheaper this is than
  H12, a null here — especially if it fails specifically on the cost
  dimension (§10.3) rather than the raw-return dimension — would replicate,
  in this project's own free-data context, the exact tension already
  documented in the literature (Chordia et al.), and would be a legitimate,
  citable data point rather than a dead end.

This is why the trial is worth spending: the question being asked is not
"does PEAD exist," it's "does *anything* survive *this specific, unusually
strict* evaluation pipeline, on *this specific, modern, cost-realistic*
sample" — an answer this project does not currently have for any hypothesis
except four nulls obtained on much more exotic, harder-to-validate data.
