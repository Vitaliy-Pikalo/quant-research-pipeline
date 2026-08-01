# Handoff: Quant Research — post-H10b, next step is breadth

Written 2026-07-31, end of session. Everything below is committed and pushed to
`https://github.com/Vitaliy-Pikalo/quant-research-pipeline`.

---

## Project context

Building an institutional-grade quant research pipeline on a strict **$0 budget**
(free/public data only), then using it to test real hypotheses against real
market data and reporting results honestly — negative or positive.

The underlying goal is to find a hypothesis that survives the full rigor stack.
Four have now been tested and none has. That is a legitimate outcome, not a
failure of the process, but it does mean the next move should be chosen on
expected information rather than convenience.

**Sandbox constraint that shapes everything:** Claude's bash sandbox reaches only
pypi.org and github.com. It cannot reach FRED, SEC EDGAR, the Fed, FDIC or
yfinance. Claude's `web_fetch` reaches more sites but is single-page and not
practical for bulk pulls. **Every real data pull is a Python script the user runs
locally.** Claude *can* read and analyse the resulting files directly, because
the user's Desktop is mounted — so the loop is: Claude writes script → user runs
it → Claude reads the output files itself.

---

## Status map

| Component | Status |
|---|---|
| Research dossier (14 hypotheses + 30 ideas) | done |
| Pipeline (`cv.py`, `stats.py`, `regime.py`, `ensemble.py`, `feature_store.py`, `costs.py`) | done, 49 pytest tests passing |
| H9 — FX carry | done — not supported (pooled IC −0.0125, p=0.073, sign flips every fold) |
| H8 — 13F copycat | done — not supported once market-adjusted |
| H10 — Beige Book district sentiment | done — not supported (IC 0.015, 0/12 districts survive FDR) |
| H10b — Beige Book, locality-weighted | done — not supported, **and it falsified the stated explanation for H10's null** |
| GitHub repo | **pushed and live**, 8 commits, pre-registration commit is a parent of the backtest commit |
| Long-form writeup (`results/POST_bugs_that_produce_results.md`) | done, linked from README |
| **H11 — breadth expansion** | **not started — this is the next step** |

**Cumulative deflated-Sharpe trial count: 78.** (H9 46 + H8 6 + H10 23 + H10b 3.)
This is carried across the whole project and must not be reset.

---

## What's been done

### Datasets built (all committed under `data/`)

| file | contents |
|---|---|
| `beige_book_sentiment_final.csv` | 131 Beige Book releases × 12 districts = 1,572 rows, 2010–2026, Loughran-McDonald scored |
| `regional_bank_prices_clean.csv` | 33 banks + KRE, daily, audited for survivorship |
| `h10b_locality.csv` | 561 bank-years of HQ-state deposit share from FDIC SOD |
| `h10b_district_assignment.csv` | FDIC-derived Fed district per constituent, incl. 3 reassignments |
| `district_constituent_report.csv` | per-constituent recovery status and reasoning |

Data quality state: all 131 release dates fall on a Wednesday (external
validation), all releases have 12 districts, word counts comparable across all
five Fed page layouts, no nulls, no duplicates.

### H10b, and why it matters more than its p-value

H10's writeup blamed the null on constituents being mapped to districts by
headquarters (U.S. Bancorp as a "Minneapolis" bet). That claim was
pre-registered, then tested once, weighting each bank by its HQ-state deposit
share from FDIC Summary of Deposits.

The fix applied correctly — locality spans 0.175 to 1.000, U.S. Bancorp's weight
in Cleveland fell to 13%, Ameris rose to 74% of Atlanta — **and the result did
not move** (IC 0.0153 → 0.0108, bootstrap p 0.72, DSR 0.0035 at 78 trials).

Reason: locality-weighted district baskets correlate with equal-weighted ones at
**0.98–0.9999**. Two to four regional banks inside a district co-move so tightly
that reweighting changes 1–2% of basket variance. **The dilution explanation is
substantially ruled out.**

### The constraint that replaced it

H10b measured effective breadth, 1/Σw²: **1.56 (Boston) to 3.34 (Cleveland)**
constituents per district. Several districts are close to single-stock bets, so
firm-specific news swamps whatever district macro signal exists.

This is measured rather than hypothesised, which is why it — not the sentiment
dictionary — is the next thing to fix.

---

## Current phase

Research line is closed out and published. Nothing is half-finished. The repo is
clean, tests pass, working tree clean, `origin/main` at HEAD.

The open question is whether to continue on the Beige Book family at all.

---

## What still needs to be done

### Option A (recommended): H11 — breadth expansion

Go from 3 banks per district to **15–25**. Directly attacks the measured
constraint. Everything else stays identical, so it is a clean single-variable
change.

**Why this and not the sentiment instrument:** a better sentiment measure still
has to push signal through baskets where one bank's idiosyncratic news dominates.
Fixing the text side cannot lift a ceiling set by the return side. Breadth is
measured; sentiment quality is speculative.

Concrete steps:

1. **Build the universe.** Need listed US regional banks with tickers.
   - SEC company tickers: `https://www.sec.gov/files/company_tickers.json` (free,
     no key, ticker ↔ CIK ↔ company name)
   - FDIC institutions API for HQ state, charter Fed district, total assets:
     `https://api.fdic.gov/banks/institutions` (free, no key)
   - Match on holding-company name. **This is a fifth hand-built mapping.** The
     previous four each contained errors. Required gates, all of which have
     already caught real errors in this project:
     - name-similarity score with a refusal threshold (caught Truist → Bank of
       America)
     - expected-state cross-check (caught United Bankshares → an Indiana thrift)
     - zero-HQ-state-deposits check (caught NYCB → the Michigan Flagstar charter)
     - minimum-observations check on price pulls (caught the recycled BRKL ticker)
2. **Filter to genuinely regional banks.** Pre-register the rule: e.g. total
   assets between $1bn and $250bn, locality ≥ 0.5, listed for the full sample.
   Fix the thresholds *before* looking at returns.
3. **Pull prices** for the expanded universe (yfinance, expect delisting failures
   — reuse `delisted_backfill.py` and `build_clean_price_panel.py` logic).
4. **Pre-register H11** in the same form as `H10b_PREREGISTRATION.md`: locality
   measure, universe rule, weighting, exact test list, decision rule, trial count.
   Commit the pre-registration *before* the backtest, as with H10b.
5. **Run once.** New trials push cumulative past 80.

Expected effective breadth after this: 10–20 per district instead of 1.6–3.3,
which is roughly a 2–3x improvement in signal-to-noise on the return side.

### Option B: sentiment instrument

Replace Loughran-McDonald, which has no negation handling and is close to a
worst case for the Beige Book's hedged prose ("modest", "slight", "little
changed", "declined less than expected"). A diffusion-index approach — counting
directional phrasing rather than sentiment words — is closer to how the Fed
actually writes. **Do this after breadth, not before**, for the ceiling reason
above.

### Option C: stop the Beige Book line

Defensible. Four negatives, 78 trials, and every further test inside this
programme raises the bar for anything found later. A genuinely independent
hypothesis, pre-registered with its own trial count, may be worth more than a
fifth pass at this one.

---

## Next step (immediate)

Ask the user to choose A, B or C. If A:

1. Write `build_bank_universe.py` — SEC tickers + FDIC institutions, with all
   four gates above, output a candidate universe CSV **and stop**. No returns.
2. Have the user run it, review the universe and the gate failures together.
3. Only then write `H11_PREREGISTRATION.md`, get sign-off, commit it.
4. Then pull prices, then run once.

Do **not** write the backtest before the pre-registration is committed. The
commit ordering is the evidence.

---

## Workflow rules

**Data and budget**

- $0 budget, free/public only. Verify a source is genuinely free before building
  on it. Stooq and Financial Modeling Prep were both abandoned this way.
- Working free sources so far: FDIC BankFind (`api.fdic.gov`, no key), SEC EDGAR,
  FRED, federalreserve.gov scraping, yfinance.
- Claude's sandbox has no general internet. Real pulls run on the user's machine;
  Claude reads the results directly from the mounted Desktop.

**Statistical rigor (non-negotiable)**

- Purged/embargoed CV, walk-forward, BH-FDR across related tests, deflated Sharpe
  against the **cumulative** trial count (currently 78, never reset), net of
  transaction costs.
- Pre-register any test designed in response to a previous null. Commit the
  pre-registration before the code that produces the result.
- No threshold tuning. Prefer continuous weighting over binary cuts so there is
  no knob to turn.
- Never carry a specification selected on one dataset into a fix designed after
  seeing that dataset's result. That is double-dipping.
- Overlapping forward windows require dependence-aware inference — block
  bootstrap resampling whole release dates, not individual observations.

**Bugs (the hard-won part)**

- **The dangerous bugs do not throw.** Six in this project produced full,
  plausible tables. Assume any clean-looking result is wrong until a gate says
  otherwise.
- **Validate against something external.** Beige Books publish on Wednesdays;
  that one check validated a date pipeline rewritten six times.
- **Distinguish "empty" from "absent".** A blank holding company is data; a
  missing year is a gap. Conflating them deleted 61 bank-years silently.
- **Build gates before you need them.** Every serious bug here was caught by an
  automated check, never by reading the table.
- **Re-derive every number in a writeup from the source files.** A stale locality
  figure survived in the draft post after the underlying data was corrected.
- Outputs folder is immutable once written — use a new filename for revisions.

**Working with the user**

- Windows `cmd.exe`: `set` not `export`; no `tail`/`head`. One command per
  message, wait for output before the next.
- Long paths break `xcopy`; use `robocopy` (exit code 1 means success).
- Desktop is mounted, so Claude should Write files directly rather than using
  Notepad + clipboard.
- TL;DR at top, concise and structured, tables over prose, plain language,
  casual lowercase tone. Ask one clarifying question at a time and only when
  genuinely blocked.
- The user asked once about backdating commits to look more human. Declined:
  this is portfolio work and a fabricated timeline misrepresents it to the
  people evaluating it. Atomic, logically-scoped commits are fine and were used.

---

## Key file locations

```
C:\Users\pikal\Desktop\quant-research-pipeline\     the repo (pushed)
  cv.py stats.py costs.py regime.py ensemble.py feature_store.py
  backtests/    all pulls and backtests incl. H10 and H10b
  data/         all committed datasets
  results/      dossier, H10 writeup, H10b pre-reg + writeup, the post
  tests/        49 tests

C:\Users\pikal\Desktop\.fdic_cache\                 cached FDIC pulls (reruns are free)
```

Reproduce H10b end to end:

```
cd /d "%USERPROFILE%\Desktop\quant-research-pipeline"
python backtests/run_h10b_backtest.py
```
