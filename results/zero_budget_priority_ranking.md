# $0-Budget Priority Ranking

Filters the research dossier's H1-H14 hypotheses and 30 original ideas down to what's
actually buildable with free/public data only. Tiering is by (a) whether a genuinely
free, official, stable data path exists, and (b) how much data-engineering labor that
path requires. Legal/ToS risk is called out separately -- "free" here always means
"free and not ToS-restricted" unless flagged otherwise.

## Core hypotheses (H1-H14), free-data feasibility

| Hyp | Free path? | Notes |
|---|---|---|
| H8 13F herding | Yes, clean | EDGAR structured 13F data, fully free. Best risk/effort ratio in the whole catalog. |
| H9 FX carry/UIP | Yes, clean | FRED (rates) + free FX APIs (OANDA/Alpha Vantage). Structural premium, not attention-decayed. |
| H13 Search attention | Yes, clean | Wikipedia Pageviews API (official, stable) beats unofficial Google Trends. |
| H2 PEAD (numeric) | Mostly free | EDGAR 8-K timestamps free; consensus-estimate data is the gap (limited free tiers only). |
| H7 Short interest | Partially free | FINRA bi-monthly short interest is free but stale; the higher-power lending-fee version is paid-only. |
| H1 Supply chain momentum | Free but heavy | EDGAR full-text extraction of customer disclosures is a real NLP/entity-resolution project. |
| H3 Index reconstitution | Mostly free | Prices free; official S&P/Russell change announcements require scraping, not a clean API. |
| H12 Earnings-call tone | Partially free | No free comprehensive transcript API; Loughran-McDonald dictionary itself is free. |
| H4, H5, H10, H11, H6, H14 | Paid-blocked or low-value | Options IV surfaces (H4/H5), alt-data panels (H11), and SDC-quality deal data (H10) are the paid-vendor-dominated categories in this catalog; H6/H14 are included as negative/low-conviction cases regardless of budget. |

## Part-4 original ideas, tiered

**Tier A -- build these first (free, clean official API, low legal risk):**
#3 patent-citation centrality (USPTO PatentsView), #6 SEC comment-letter NLP (EDGAR),
#9 state bill tracking (LegiScan), #10 customs/reshoring (UN Comtrade), #12 litigation
docket signal (CourtListener/RECAP), #13 Wikipedia edit velocity, #14 board-interlock
network (EDGAR DEF 14A + Form 4), #15 muni-issuance regional-bank proxy (EMMA),
#19 GitHub commit velocity, #20 Beige Book district NLP (longest, cleanest free
history in the list -- 8 releases/year back decades), #22 VIIRS nighttime lights
(NOAA/NASA + Google Earth Engine free tier), #25 arXiv preprint velocity (arXiv
portion only), #27 board-departure clustering (EDGAR 8-K).

**Tier B -- free but labor-intensive data engineering:**
#1 corporate-jet tracking (OpenSky Network / ADS-B Exchange free tiers + FAA
registry), #4 utility-filing capex nowcast (state PUC dockets, fragmented),
#17 FCC tower-permit tracking (national API free, local zoning is county-by-county),
#18 vocal-biomarker earnings-call analysis (free audio + open-source acoustic
tools, but a real ML-engineering build), #21 county unemployment/WARN cross-reference
(BLS free, WARN databases fragmented across 50 states), #29 gaming
player-count/livestream data (SteamDB scrape + free Twitch API).

**Tier C -- partially free, capped statistical power:**
#7 app-store ranking/review velocity (SimilarWeb free tier is limited), #11 ENSO
forecast vs. commodity pricing (NOAA free, but the commodity-options side likely
needs a paid feed for anything beyond delayed data), #16 cat-bond/FEMA divergence
(FEMA free, cat-bond pricing is a paid ILS-data product), #23 dark-pool/GEX
combination (FINRA aggregate free, but the more powerful signed-large-trader data
genuinely isn't public).

**Tier D -- ToS-restricted or effectively paid-blocked at $0:**
#2 job-posting velocity (LinkedIn/Indeed scraping, ToS risk; Revelio Labs paid),
#5 customs bill-of-lading (ImportGenius/Panjiva paid resellers), #8 employee-review +
options-skew (Glassdoor scraping ToS risk + paid options data), #26 ADR
tick-level arbitrage (meaningful history needs Databento/Polygon paid tiers),
#28 sublease-listing data (LoopNet scraping ToS risk, no free bulk source).

**Tier F -- not realistically buildable at $0:**
#24 aviation-insurance distress signal (no public per-company data path exists),
#30 hedge-fund-letter narrative crowding (no legal, comprehensive, free letter
archive exists at any scale).

## Recommended build order at $0 budget

1. **H8 (13F herding)** -- cleanest free data, real academic backing, fastest to a
   genuine first backtest.
2. **H9 (FX carry)** -- structural premium, not attention-decayed, free FRED + FX data.
3. **Idea #20 (Beige Book district NLP)** -- longest clean free history in the whole
   list, genuinely untested angle (district-level vs. national-level reaction).
4. **Idea #13 (Wikipedia edit velocity) as a feature alongside H13** -- official,
   stable, free, and a direct incremental-information test against the
   already-well-known Google Trends signal.
5. **Idea #14 (board-interlock network)** -- highest novelty-to-cost ratio in Tier A,
   but budget real time for the entity-resolution work before expecting results.

Everything else in Tier A/B is a reasonable second-wave pick once the pipeline
(`quant_pipeline/`) is validated against real data from picks 1-2 above.
