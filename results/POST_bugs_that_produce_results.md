# The bugs that don't crash

I spent a weekend testing four market-inefficiency hypotheses on real data, with a $0 budget and only public sources. All four came back negative.

That's not what this post is about. Negative results are the ordinary outcome of honest testing, and a repo full of them is only interesting for one reason: of the roughly dozen bugs I hit along the way, **the dangerous ones never threw an exception**. They produced a full, plausible-looking table of numbers. A few of them would have produced a *result* — something I could have written up, put on GitHub, and been quietly wrong about in public.

This is a catalogue of those bugs, what caught them, and the one experiment where I pre-registered my own explanation for a null result and watched it fail.

Code and data: [`quant-research-pipeline`](https://github.com/Vitaliy-Pikalo/quant-research-pipeline).

---

## The setup, briefly

The pipeline implements the standard institutional hygiene: purged and embargoed cross-validation, Benjamini-Hochberg FDR across batches of related tests, deflated Sharpe ratios, a point-in-time feature store, and a transaction cost model. 49 tests, and writing them caught a genuine unit-mismatch bug in the deflated Sharpe implementation that was flattening strong signals to zero at only 20 trials.

Four hypotheses went through it:

| | hypothesis | result |
|---|---|---|
| H9 | FX carry / UIP violation | not supported. Pooled IC −0.0125, sign flipped in every walk-forward fold |
| H8 | 13F copycat investing | not supported. The raw "edge" was market beta; negative once adjusted |
| H10 | Beige Book district sentiment | not supported. IC 0.015, 0 of 12 districts survive FDR |
| H10b | H10 with the constituent flaw repaired | not supported — and the reason is the interesting part |

One number ties them together. The deflated Sharpe ratio penalises a result for how many things you tried before finding it, and I carried that count **cumulatively across the whole project** rather than resetting it per hypothesis: 46 trials from H9, 6 from H8, 23 from H10, 3 from H10b. By the end, 78.

Resetting the count each time you start a "new" hypothesis is the most common way this correction gets quietly defeated. It's also completely invisible in a writeup unless the author tells you.

---

## The catalogue

### 1. A date that was five weeks early

The Federal Reserve publishes the Beige Book eight times a year. Each release lives at a URL containing a six-digit stem — `202505`, say.

`202505` is the **May 2025** Beige Book. It was published on **4 June 2025**.

The stem is the *period*, not the publication date. My first scraper couldn't parse the date for five releases and fell back to a placeholder of the first of the stem month. So for those five, forward returns were measured from roughly five weeks before the information was public.

That is look-ahead bias, and it points in the direction that manufactures signal. It would not have crashed anything. It would have produced a slightly better-looking result.

The fix was to stop inferring the date and read it from the PDF each release links: `files/BeigeBook_20250604.pdf`. The filename *is* the publication date.

The check that made me trust it: **every Beige Book is published on a Wednesday.** All 131 release dates in the final dataset land on a Wednesday. That test costs one line and validates against something outside the dataset, which is the only kind of validation worth much.

### 2. Eight hundred words of navigation menu, scored as sentiment

The Fed has changed its page template four times since 2010. From 2024 the release is split across one page per district, and my scraper extracted those pages whole — including the site's navigation menu, the cookie banner, the footer.

The fingerprint:

| layout | n | mean word count | polarity std |
|---|---|---|---|
| old (2011–2016) | 552 | 616 | 0.231 |
| single page (2017–2023) | 659 | 640 | 0.233 |
| **split (2024–2026)** | **252** | **1496** | **0.142** |

Roughly 850 words of identical boilerplate in every observation, diluting the sentiment score toward zero and compressing its variance by 40%.

Think about what that does downstream. The design scores each district against its own trailing baseline. A sudden variance compression, arriving simultaneously in all twelve districts, on the exact date the Fed changed its template, reads to that model as a real, simultaneous, cross-district sentiment shift. A backtest can find that. It would be entirely an artifact of my scraper.

The fix was one extraction rule for every era: start at the district's own heading tag, stop at the footer. Never score a whole page. Afterwards all five layouts sit between 587 and 661 mean words.

### 3. The missing tickers were not missing at random

The price pull reported four failures out of 36: BHLB, NYCB, SNV, CMA. Delisted, said yfinance.

Every one of them was an acquisition target. Berkshire Hills merged into Beacon Financial. NYCB renamed itself Flagstar. Synovus went into Pinnacle. Comerica was bought by Fifth Third and delisted in February 2026.

Acquisition announcements are large positive return events. Dropping precisely the acquired names is textbook survivorship bias, and the failure message frames it as a data availability problem rather than a sample selection one.

I recovered two of the four by verifying against price behaviour rather than the corporate story. BBT matches Berkshire Hills' price history and runs continuously across BB&T's ticker retirement, so it's the same listing renamed — accepted. FLG falls 38% on 31 January 2024, exactly matching NYCB's collapse — accepted.

The other two I rejected. The Comerica "successor" series was **bit-identical** to the Fifth Third already sitting in the Cleveland basket; using it would have put one bank's returns into two districts and manufactured cross-district correlation out of nothing. Pinnacle is simply a different company.

### 4. The ticker that came back as somebody else

BRKL — Brookline Bancorp — did not appear in the failure list at all. It downloaded cleanly.

It returned 18 rows, starting 7 July 2026.

Brookline merged into Beacon in September 2025 and the ticker was subsequently **recycled onto an unrelated instrument**. The download succeeded. The data was real. It belonged to a different company.

This is the one that worries me most, because there was no error to notice and no failure list to read. It surfaced only because I printed per-ticker date ranges and 18 rows looked wrong next to everyone else's 4,169. The general fix now lives in the pipeline: any ticker returning under 100 observations is flagged as a possible recycled symbol.

### 5. The biggest bank in North Carolina

For H10b I needed to match 33 tickers to FDIC institutions. My resolver filtered candidates to the expected state, then picked the largest by assets.

Truist is headquartered in Charlotte. So is Bank of America, and it's about five times the size.

Every Truist number in my first locality table — 39 states, top state California, locality 0.128 — was Bank of America's. Size is not evidence of identity, and I'd thrown away the actual signal (name relevance) in favour of a proxy that happened to be wrong in exactly one case out of 33.

Two more mis-resolutions came out of the same mapping. "United Bank" matched an unrelated Indiana thrift owned by a company called PEDCOR before it found United Bankshares. And New York Community Bancorp resolved to the *Flagstar* charter, which was a Michigan thrift until 2022 — attaching a decade of Michigan deposits to a New York district constituent.

All three were caught by automated gates, not by me reading the table. The NYCB one surfaced because I'd added a check for *zero deposits in a bank's own headquarters state* — which is not a plausible bank, and is a reliable signature of a charter-continuity error.

That's the fourth hand-built mapping in this project. The previous three all contained errors too. I don't trust this one more because I was more careful; I trust it more because it's the first one with gates around it.

---

## The part I'm actually proud of

H10 came back null, and I wrote down why I thought it might be a *false* null.

Constituents were assigned to Federal Reserve districts by headquarters. U.S. Bancorp is a $600bn national bank nominally representing Minneapolis. Truist is a national franchise nominally representing Richmond. If a district's basket is dominated by banks that don't earn their money in that district, any real district-level effect gets diluted to zero by construction.

The tempting move here is obvious: re-run on a "local banks only" subset and see if the result improves. I didn't, and the reason is that a subset rule invented after seeing a null is a free parameter. Choosing the one that rescues your hypothesis is precisely the failure the whole pipeline exists to prevent.

So I pre-registered it instead. [The document](H10b_PREREGISTRATION.md) fixes the locality measure, the point-in-time rule, the weighting scheme, the exact list of tests, and a four-part decision rule — all before any FDIC data was pulled. It sits in the repo as its own commit, and that commit is a **parent** of the backtest commit. You don't have to take my word that the prediction came first.

Two design choices worth flagging. There's no threshold — constituents are weighted *continuously* by locality rather than filtered at 50% or 60%, because a cut point is a knob I could turn until the answer changed. And the `chg` feature that had produced H10's near-miss was deliberately excluded, because carrying a spec selected on H10's data into a fix designed after seeing H10's null is double-dipping.

**The fix worked. The result didn't move.**

Locality scores span 0.175 to 1.000 as a per-bank average, and 0.213 to 1.000 in the latest vintage — a 4.7x spread. Rockland Trust and Frost Bank score 1.000, genuinely single-state banks. U.S. Bank scores 0.12 to 0.23 across 28 states. U.S. Bancorp's weight in Cleveland fell to 13%; Ameris rose to 74% of Atlanta.

And the pooled IC went from 0.0153 to 0.0108. Bootstrap p of 0.72. One of four pre-registered criteria met.

Before concluding anything I checked the fix had actually applied, because a repair that silently fails to take produces a null that looks identical to a real one. It had. The weights were right, the point-in-time rule was right, the arithmetic checked out against an independent recompute.

**Why it didn't matter is the finding.** The locality-weighted district baskets correlate with the equal-weighted ones at 0.98 to 0.9999. Two to four regional banks inside one district co-move so tightly that reweighting them changes 1–2% of basket variance. The "local" bank and the "national" bank move together because both trade on the same national rate and credit cycle.

My explanation for the H10 null was wrong, and now I know that rather than suspecting it.

The test also produced something I hadn't set out to find: measured effective breadth, 1/Σw², runs from 1.56 to 3.34 constituents per district. Several districts are close to single-stock bets. That's a real constraint, it's measured rather than guessed, and it means the next thing to fix is the number of banks per district — not, as I'd previously assumed, the sentiment dictionary.

---

## What I'd tell someone building this

**Validate against something outside your dataset.** Beige Books publish on Wednesdays. That one fact, checked in a single line, independently confirmed a date-extraction pipeline I'd rewritten six times. Internal consistency checks can't catch a systematically wrong date; an external one can.

**Distinguish "empty" from "absent".** Half my data bugs came from conflating them. A bank reporting no holding company is not the same as a bank missing from that year. A ticker returning 18 rows is not the same as a ticker returning none. Blank is data.

**Build the gates before you need them.** Every serious bug here was caught by an automated check, not by inspection. I looked directly at the table containing Bank of America's footprint under Truist's ticker and did not see it. The coverage gate, the name-similarity gate and the zero-HQ-deposits gate all fired on things my eyes had already passed over.

**Write down why you think you're wrong, then test it.** The most informative result in the project is the one where my own stated explanation got falsified. It cost three trials and it closed off a line of reasoning I'd otherwise still be assuming.

**Count your trials across the whole project.** Not per backtest, and not per hypothesis. H10's most promising specification looked like a 0.94-probability result treated in isolation. Against 75 trials it was 0.18. The gap between those two numbers *is* the selection bias, and it's arithmetic, not judgement.

Four hypotheses, four negatives, and a dozen bugs that would have quietly improved my results. I'd rather publish that than a backtest with a nice equity curve and no error bars.

---

## Postscript

While fact-checking this post against the data files, I found one more.

The paragraph about locality scores originally read "0.125 to 1.000". That 0.125 was NYCB — from *before* I corrected the Flagstar charter mix-up described in section 5. I'd fixed the data, re-run everything, and left the number sitting in my prose where it no longer belonged. It's off by 40% and it reads as completely plausible.

A stale figure in a writeup is the same species as everything above: no error, no warning, a number that looks fine. The only reason I caught it is that I'd made a habit of re-deriving every stated number from the source files instead of trusting the draft.

Which is the whole point. You don't outgrow this failure mode by being careful. You outgrow it by building something that checks.
