




# Institutional Quant Research Dossier
### Statistically Testable Market Inefficiencies, an Automated Discovery Pipeline, and 30 Original Research Ideas

Prepared for: independent quantitative researcher (Python + cloud compute)
Scope: causal/structural inefficiencies over retail technical signals; peer-reviewed and hedge-fund-grade sourcing throughout.

---

## 0. How to read this document

- **Part 1** — 14 institutional-grade hypotheses, each with the full 12-point breakdown you specified.
- **Part 2** — Ranking matrix across Expected Alpha, Implementation Difficulty, Data Cost, Competition, Novelty, Scalability.
- **Part 3** — A complete automated research pipeline (feature generation → ensembles) designed to discover new relationships rather than manually test ideas one at a time.
- **Part 4** — 30 original, non-mainstream research ideas, each with an exact backtest specification.

Every claim about historical evidence is sourced from peer-reviewed journals, NBER/SSRN working papers, or named practitioner research; sources are listed at the end. Where evidence is contested, both sides are shown — that contest is itself part of the signal (it tells you where the edge is fragile).

---

## PART 1 — CORE HYPOTHESIS CATALOG

### H1. Customer–Supplier Information Diffusion (Economic-Link Momentum)

**Theory.** Investors have limited attention and process news about a firm's direct economic partners (major customers, suppliers) with a lag, because that information requires linking two separate disclosures (a customer's earnings call to a supplier's 10-K "significant customer" footnote). Information diffuses slowly across the supply-chain graph, producing predictable drift in the supplier's price after a customer shock. This is a **causal information-transmission** story, not a risk premium — it should not survive if attention constraints disappear.

**Markets affected.** US equities primarily; extendable to any market with mandatory customer-concentration disclosure (Canada, UK, Australia via similar segment-reporting rules).

**Securities affected.** Small/mid-cap suppliers with concentrated customer bases (semiconductor equipment, auto parts, contract manufacturers, specialty chemicals) tied to large, widely-covered customers (Apple, Walmart, automakers).

**Required datasets.** Compustat customer segment data (FactSet Supply Chain Relationships, Bloomberg SPLC), CRSP/daily prices, earnings announcement dates, SEC EDGAR full-text (10-K Item 1/Exhibit 21 customer disclosures).

**Public APIs.** SEC EDGAR full-text search API (free) to extract "major customer" disclosures; Polygon.io/Tiingo/IEX Cloud for daily prices; FactSet/Bloomberg supply-chain linkage feeds are the institutional-grade paid alternative (no free equivalent with comparable coverage).

**Historical evidence.** Cohen & Frazzini (2008, *Journal of Finance*), "Economic Links and Predictable Returns": a supplier long/short strategy sorted on customer returns earns ~1.45%/month, Fama-French-3 alpha, t = 3.61 (~18.4%/yr gross, pre-cost). Effect survives controls for own-momentum, industry momentum, and cross-industry lead-lag.

**Statistical significance.** t = 3.61 in the original sample (1980s–2000s); subsequent out-of-sample replication confirms the sign and direction but with a **smaller** coefficient post-publication (2023 replication literature, "Customer Momentum," arXiv:2301.11394) — a textbook example of post-publication decay.

**Decay.** Substantial. Post-2008 publication, the effect attenuates as quant funds systematized supply-chain linkage data (FactSet Supply Chain product launched partly in response to this literature). Still statistically present in less-covered, smaller-cap linkages where data vendors have incomplete graphs.

**Implementation difficulty.** Medium-high. The hard part isn't the trade — it's building/maintaining a clean, point-in-time customer-supplier graph without survivorship or look-ahead bias (relationships must be dated to disclosure date, not discovery date).

**Possible improvements.** (a) Extend to 2nd/3rd-degree links (customer-of-customer) where institutional coverage is thinner; (b) combine with earnings-call transcript NLP to detect *unstructured* mentions of customers not captured in structured segment data; (c) weight by analyst-coverage overlap (low overlap = slower diffusion = bigger effect).

**How institutions already exploit it.** Systematic multi-strategy funds (AQR, which co-published the original paper, and several multi-manager platforms) run supply-chain-linkage books; FactSet/Bloomberg sell the linkage data specifically because of this literature.

**Individual edge.** Thin but nonzero. An individual can still profitably mine the long tail of small-cap/micro-cap linkages that data vendors under-cover, using EDGAR full-text search to build a proprietary graph institutions haven't fully systematized. Capacity is naturally self-limiting (illiquid small caps), which is exactly why it survives for a small account.

---

### H2. Post-Earnings-Announcement Drift, Text-Augmented (PEAD.txt)

**Theory.** Markets underreact to earnings surprises because investors anchor on the *numerical* surprise (actual vs. consensus EPS) and under-weight information in the *qualitative* delivery (MD&A language, guidance phrasing, analyst Q&A tone). Drift is a compensation for costly information processing, not risk — bounded rationality, not a priced risk factor.

**Markets affected.** US, EU, and Japanese equities with analyst coverage; strongest in mid-caps with moderate (not zero, not saturated) analyst coverage.

**Securities affected.** Common equities with quarterly earnings + earnings-call transcripts; strongest where surprise is large and institutional ownership is moderate (limits arbitrage capital).

**Required datasets.** I/B/E/S consensus estimates, earnings-call transcripts (Capital IQ Transcripts, AlphaSense, Refinitiv StreetEvents), CRSP/Compustat, SEC 8-K/10-Q filing timestamps.

**Public APIs.** SEC EDGAR (8-K timestamps, free); Financial Modeling Prep / Alpha Vantage / Finnhub for earnings surprise data (partial free tiers); no comprehensive free transcript API — Seeking Alpha and Motley Fool transcripts are scrapeable but ToS-restricted; institutional-grade is Refinitiv/AlphaSense (paid).

**Historical evidence.** Ball & Brown (1968) documented the base drift; Meursault, Liang, Routledge & Scanlon (2023, *forthcoming*), "PEAD.txt," show a text-based surprise measure produces PEAD that is **stronger and more persistent** than the numeric-EPS version, robust 2008–2019.

**Statistical significance.** Base numeric PEAD historically ~t > 4 pre-2000s; text-augmented version in Meursault et al. shows comparable or higher significance in a sample where numeric PEAD had allegedly weakened.

**Decay.** **Actively disputed in the literature** — this is a rare case where you should treat the disagreement itself as the research question. Martineau (2022) claims numeric PEAD vanished from non-microcap stocks by 2006 (decimalization + faster arbitrage). Two 2025 papers (per UCLA Anderson research brief, Subrahmanyam commentary) contradict this and find PEAD "alive and well," attributing the discrepancy to research-design choices (surprise measurement window, standardization method, sample filters). **Actionable insight**: before trading PEAD, replicate both methodologies on your own point-in-time data — the answer depends on definitional choices you control.

**Implementation difficulty.** Medium. Numeric version is a one-afternoon backtest; text version requires an NLP pipeline (transcript scraping, embedding/sentiment scoring, alignment to filing timestamps) — a multi-week build.

**Possible improvements.** Use LLM-based zero-shot classification of guidance sentiment instead of bag-of-words dictionaries (Loughran-McDonald); condition drift-capture strategy on the numeric-vs-text surprise **divergence** — biggest edge is when text tone contradicts the numeric surprise.

**How institutions already exploit it.** Every major systematic equity manager (Two Sigma, WorldQuant, AQR, Man Numeric) runs an earnings-surprise/drift book; NLP-on-transcripts overlays are now standard at any fund with an alt-data budget.

**Individual edge.** Low-to-moderate on liquid large caps (fully arbitraged); moderate on small/mid-caps with transcripts but thin analyst coverage, where big funds' capacity constraints keep them out.

---

### H3. Passive Index Reconstitution Price Pressure (a documented *decaying* edge — instructive case study)

**Theory.** When a stock is added to a widely-tracked index (S&P 500, Russell 1000/2000), index funds must buy it on the effective date, creating inelastic, price-insensitive demand. Shleifer (1986) and Harris & Gurel (1986) formalized this as a **downward-sloping demand curve** argument against market efficiency: price pressure should be transitory (pure demand shock) unless there's an information effect (index inclusion as a certification signal).

**Markets affected.** US equities (S&P 500/1000/600, Russell 1000/2000/3000), and any market with high passive-AUM penetration (increasingly EU, Japan).

**Securities affected.** Newly announced index adds/deletes, especially in Russell's May reconstitution (rules-based, mechanical, heavily gamed).

**Required datasets.** Index membership change announcements (S&P Dow Jones Indices, FTSE Russell methodology docs), daily/intraday prices and volumes, passive AUM tracking estimates per index.

**Public APIs.** No clean free API for index-change announcements (must scrape S&P/Russell press releases or use paid feeds like Bloomberg INCL); prices via Polygon/IEX; passive AUM proxies via ETF.com or fund-flow data (ICI, Morningstar Direct - paid).

**Historical evidence.** Historically, cumulative abnormal return from announcement to effective inclusion ≈ 6% (multiple studies, 1990s–2000s); year-after performance shows deletions have historically outperformed additions by a spread of up to ~22% in some samples — consistent with overreaction/reversal, not pure permanent price-pressure.

**Statistical significance.** Strong and significant in every pre-2010 sample (t typically > 5 for the announcement-window effect).

**Decay.** **Confirmed and quantified.** Greenwood & Sammon, "The Disappearing Index Effect" (NBER WP 30748 / HBS WP 23-025): Russell 1000/2000 inclusion and reconstitution effects have **materially declined over the past decade**, attributed to (a) growth of substitute liquidity providers who front-run and arbitrage the rebalance, (b) index providers' own moves to reduce predictability (e.g., banding rules, phased implementation), and (c) crowding by dedicated "index arb" desks that now front-run the front-runners.

**Implementation difficulty.** Low-to-medium for the mechanical trade; high for finding *residual* alpha now that the obvious trade is crowded out.

**Possible improvements.** Trade the *predicted* reconstitution list weeks before the official announcement using the public, rules-based methodology (float-adjusted market cap thresholds are computable from public data) — this is where remaining edge lives, not in trading the announcement itself. Also exploit smaller/less-tracked indices (S&P MidCap 400, sector indices, thematic ETF rebalances) where crowding is lower.

**How institutions already exploit it.** Dedicated index-arbitrage desks at every bank and several quant funds (e.g., BlackRock's own transition-management desk internalizes flow to avoid paying the spread) have compressed this to near zero on S&P 500/Russell 1000. This is presented deliberately as a **decayed-edge case study**: it's the textbook example of an anomaly discovered, published, and arbitraged away within roughly a decade — useful as a calibration point for judging how much time you have on any *new* anomaly you find.

**Individual edge.** Very low on large-cap indices now. Moderate on illiquid small-cap/thematic ETF reconstitutions where AUM tracking a given index is small enough that professional arb desks don't bother.

---

### H4. Option-Implied Volatility Skew and Spread as Informed-Trading Signals

**Theory.** Informed traders with negative private information prefer to trade OTM puts (leverage + limited downside on the option premium); informed traders with positive information prefer ATM calls. This shifts the **skew** (OTM put IV − ATM call IV) and the **IV spread** (call IV − put IV) ahead of the information becoming public in the stock market, because options markets have lower transaction-cost frictions for leveraged directional bets than shorting stock.

**Markets affected.** US single-name equity options market (most liquid); extendable to index options for market-level informed flow.

**Securities affected.** Optionable stocks with liquid OTM put and ATM option markets — most effective in mid/large-cap names with active options chains but where stock-borrow costs make short-selling expensive (skew signal is strongest exactly where short-sale constraints bind).

**Required datasets.** OptionMetrics IvyDB (institutional standard) or CBOE DataShop for historical option chains and computed Greeks/IV surfaces; daily equity prices.

**Public APIs.** ORATS and Polygon.io options endpoints provide IV surfaces at retail-accessible pricing; CBOE LiveVol/DataShop for historical (paid); no free comprehensive historical options IV database exists at institutional quality.

**Historical evidence.** Xing, Zhang & Zhao (2010, *JFQA*): steeper OTM put skew predicts significantly lower future stock returns — informed put buying ahead of bad news. Cremers & Weinbaum (2010): positive call-put IV spread predicts significantly higher future returns. Both effects robust to standard risk-factor controls (size, value, momentum, liquidity).

**Statistical significance.** Original papers report highly significant portfolio-sort spreads (annualized alpha in the mid-single-digit percentages, t-stats typically 3–5) after controlling for the Fama-French-Carhart factors.

**Decay.** Options markets are more institutionally dominated and more efficiently arbitraged than equities (market-maker inventory management is highly systematic), so *raw* skew/spread signals have likely decayed for large, liquid names since original publication (2010–2011). Less-crowded in mid-caps with wider option spreads where market-making capital is scarcer.

**Implementation difficulty.** High. Requires building a clean, point-in-time options-surface dataset (strike/expiry interpolation, removing stale quotes, handling corporate actions in strikes) — this data engineering burden is the real barrier, not the signal logic.

**Possible improvements.** Condition the signal on short-sale constraint proxies (borrow fee, days-to-cover) — the theoretical mechanism predicts the effect should be strongest exactly where stock-market informed trading is most costly, i.e., where skew signal and short-interest signal (H7) should interact multiplicatively, not additively.

**How institutions already exploit it.** Volatility-arbitrage and stat-arb desks (Citadel, Susquehanna, Jane Street market-making arms) monitor skew/IV-spread continuously as part of options market-making risk management, which is itself a form of continuous exploitation/arbitrage that compresses the signal.

**Individual edge.** Moderate in mid-cap names with wide bid-ask option spreads that deter high-frequency options market makers from fully correcting the mispricing, but transaction costs (wide spreads, need for options-approved brokerage, margin) eat into the edge for a small account.

---

### H5. Dealer Gamma Exposure (GEX) and Regime-Dependent Volatility

**Theory.** Options market makers hedge delta continuously. When dealers are net **long gamma** (typical when retail/institutional flow is net option-buying, e.g., post-crash hedging demand), their hedging is **counter-trend** (sell into rallies, buy into dips), which mechanically dampens realized volatility. When dealers are net **short gamma**, hedging is **pro-cyclical** (sell into dips, buy into rallies), amplifying moves. This is a genuinely **causal, mechanical** (not behavioral) relationship — a rare case in this list where the causal chain is close to first-principles arbitrage-free reasoning rather than an inferred behavioral bias.

**Markets affected.** US equity index options (SPX, SPY) primarily, where dealer positioning is large relative to underlying float; extendable to single-name mega-caps (NVDA, TSLA, AAPL) with heavy options open interest relative to float.

**Securities affected.** SPX/SPY/QQQ and their constituents indirectly via correlated hedging flows; single names with options open interest that is large relative to average daily traded volume.

**Required datasets.** Full options chain OI and Greeks by strike/expiry (to construct dealer positioning proxy under standard assumptions about customer vs. dealer side), realized/implied volatility term structure.

**Public APIs.** SpotGamma, SqueezeMetrics (GEX originator), and Tradytics offer commercial GEX feeds; CBOE/OCC publish aggregate OI (free) but not signed dealer positioning — signed positioning (who's net long/short) is inferred, not directly observed, which is the core methodological weakness of every public GEX product.

**Historical evidence.** Recent quantitative studies (2024–2025 practitioner research, e.g., Harbourfront Quant substack replications of the SqueezeMetrics methodology) find GEX and its derivative have a statistically significant relationship with subsequent SPX returns and next-day realized volatility, robust across pre- and post-2020 subperiods, though **weaker post-2020**.

**Statistical significance.** Practitioner-grade evidence (not top-journal peer review — this is an area where the best public research is from quant-fintech blogs and industry papers, not academic journals) shows modest but consistent incremental R² over VIX-only models for next-day volatility forecasts.

**Decay.** Partially decayed and structurally noisy: public GEX estimates carry an estimated 30–50% error margin because dealer net positioning must be *inferred* (via open-interest change heuristics and assumed customer/dealer sidedness), not observed directly. The mechanical hedging story is real; the tradeable-signal story is thinner and fails specifically during regime breaks (sovereign crises, commodity squeezes, currency-peg breaks) — exactly the periods where the payoff would matter most.

**Implementation difficulty.** Medium (constructing your own GEX proxy from public OI data is a well-documented methodology) to high (getting genuinely signed dealer flow, which requires paid OCC large-trader or FINRA data).

**Possible improvements.** Combine GEX level with its **rate of change** (dGEX/dt) rather than level alone — evidence suggests the derivative carries more information than the level; validate against realized intraday vol-of-vol rather than close-to-close returns, since the mechanism operates intraday.

**How institutions already exploit it.** Every options market-making desk manages gamma exposure as core risk management (this is definitionally what they do), so the "signal" institutions exploit isn't GEX itself — it's trading *against* the retail/systematic community that has begun front-running publicly-known GEX levels (0DTE options flow is now explicitly studied as a GEX-distortion factor since 2023).

**Individual edge.** Low-moderate. The raw concept is now widely disseminated (SpotGamma has a large retail following), meaning the naive version is crowded; edge exists in more careful signed-flow estimation or single-name application beyond SPX/QQQ where fewer players build the infrastructure.

---

### H6. Order Flow Toxicity (VPIN) — a Contested, Cautionary Case Study

**Theory.** VPIN (Volume-Synchronized Probability of Informed Trading, Easley/López de Prado/O'Hara 2011) proposes that volume-bucketed order-flow imbalance measures the probability that a given trade is "informed," and that a run-up in informed-trading probability should precede liquidity crises (market makers withdraw when adverse selection risk rises) — a genuinely causal microstructure story linking information asymmetry to liquidity provision.

**Markets affected.** Highly liquid futures/equity markets where high-frequency tick data is available (originally applied to E-mini S&P 500 futures around the 2010 Flash Crash).

**Securities affected.** Liquid index futures and large-cap equities with dense tick data.

**Required datasets.** Full tick-by-tick trade and quote data (NYSE TAQ, CME MDP 3.0) — this is genuinely institutional-scale data (terabytes/year for full US equity tape).

**Public APIs.** Polygon.io and Databento offer historical tick data at retail-accessible (if not cheap) pricing; full TAQ from NYSE is the institutional benchmark (very expensive).

**Historical evidence.** The original 2011 paper claimed VPIN reached record highs *before* the May 6, 2010 Flash Crash, positioning it as an early-warning liquidity-crisis indicator.

**Statistical significance / contested evidence.** This is the most important **negative-result case study** in the list. Andersen & Bondarenko (2014, using S&P 500 futures tick data) found VPIN is **mechanically correlated with volume and volatility by construction** and has **no incremental predictive power** for future volatility once current volume/volatility are controlled for. Further critiques found VPIN reached its documented peak **after**, not before, the Flash Crash began, and that results are highly sensitive to the trade-classification algorithm (Lee-Ready vs. bulk volume classification) used to build it.

**Decay/status.** Never robustly established as an out-of-sample predictive signal once properly controlled — arguably "decayed" before it ever worked as advertised. Included here deliberately: the original VPIN papers are widely cited and frequently proposed by newcomers to quant finance, and a rigorous researcher needs to know this is a **methodologically disputed** indicator, not an established edge, before spending engineering time on it.

**Implementation difficulty.** High (tick-level data engineering, volume-clock bucketing, trade classification) for a signal whose incremental value over trivial volume/volatility controls is, per the peer-reviewed replication literature, close to zero.

**Possible improvements.** If pursuing this family of research, use it as a **feature**, not a standalone strategy — feed VPIN-style order-imbalance measures into a broader ML ensemble (Part 3) alongside volume/volatility controls, and let feature-selection/SHAP analysis (not prior belief) determine whether it earns a nonzero weight. Also worth testing bulk-volume-classification-free alternatives (e.g., Amihud/Kyle's-lambda-based toxicity proxies) that don't share VPIN's mechanical volume confound.

**How institutions already exploit it.** Some market-making/HFT desks use order-imbalance measures broadly (not VPIN specifically) for adverse-selection risk management in quoting — but this is closer to "necessary market-making infrastructure" than "alpha signal."

**Individual edge.** Essentially none as a standalone tradeable signal per the peer-reviewed replication literature — but it's a useful, well-documented example of a plausible-sounding causal story that failed replication, worth internalizing before trusting other microstructure claims without checking for a mechanical confound.

---

### H7. Short Interest / Securities-Lending-Fee Anomaly

**Theory.** Short sellers are on average better informed than the marginal long investor (higher analytical sophistication, higher cost of entry deters uninformed shorting). High short interest and, more precisely, high securities-lending fees (a market-based, continuously updated measure of short-sale constraint and demand) should negatively predict future returns — this is a **costly-information/informed-trading** causal story, closely related to H4's options mechanism but observed directly in the lending market rather than inferred from options.

**Markets affected.** US and international equities with active securities-lending markets.

**Securities affected.** High-short-interest, "special" (hard-to-borrow) stocks — small/mid-cap, high-short-squeeze-potential names.

**Required datasets.** Exchange-reported short interest (bi-monthly, FINRA), securities-lending fee/utilization data (Markit Securities Finance / IHS Markit, S3 Partners — both paid, institutional-grade).

**Public APIs.** FINRA short-interest data is free but low-frequency (twice monthly) and lagged; daily short-volume data (not short interest) is available via FINRA's Daily Short Sale Volume files (free); real-time borrow-fee/utilization data (the more powerful signal) is paid-only (IHS Markit, S3 Partners, Orbisa).

**Historical evidence.** Extensive literature (surveyed via "The Growth and Limits of Arbitrage: Evidence from Short Interest," HBS) confirms short interest negatively and significantly predicts future returns, strongest among high-short-sale-potential (SSP) stocks; lending-market shocks (fee spikes) carry independent predictive power beyond static short-interest levels.

**Statistical significance.** Consistently significant across decades and international samples (t-stats typically 3+ in long-only and long/short sorts).

**Decay.** Documented and quantified in the general anomaly-decay literature: post-publication decay is substantial, and "as capital devoted to anomalies rises, profitability decays more rapidly following initial portfolio formation" — this is a general finding (not specific to short interest) but directly applicable, since short interest is one of the most heavily monitored anomalies by both academics and practitioners.

**Implementation difficulty.** Low for the free, lagged, bi-monthly short-interest version; medium-high for the higher-frequency, higher-power lending-fee version (requires a paid data subscription).

**Possible improvements.** Combine short interest **level** with lending-fee **rate of change** (a fee spike with unchanged reported short interest indicates fresh, urgent demand to short — a timelier signal than the lagged interest figure); cross with insider-buying (Form 4) as a contrarian confirmation/disconfirmation filter.

**How institutions already exploit it.** Quant long/short equity funds systematically incorporate short-interest and borrow-cost factors; prime brokers sell aggregated securities-lending data specifically to feed this trade.

**Individual edge.** Low on the free bi-monthly data (too stale, too well-known); moderate if you can afford a lending-fee data subscription and focus on small/micro-cap names where fewer funds have capacity to trade (short-selling small caps carries real execution/borrow-availability constraints that cap institutional capacity — the same friction that generates the edge also limits who can harvest it).

---

### H8. 13F Institutional Herding / Copycat Decay

**Theory.** Skilled fund managers' quarterly 13F disclosures reveal *some* residual information even after the mandatory reporting lag, because portfolio construction reflects longer-horizon convictions that don't fully decay in 45 days for lower-turnover managers — but for high-turnover/quant managers, the position may already be closed by the time it's disclosed, making the disclosed information stale or actively misleading.

**Markets affected.** US equities (13F is a US SEC requirement); comparable disclosure regimes exist in UK (major shareholding notifications) and EU (Transparency Directive).

**Securities affected.** Concentrated positions of identifiably skilled, low-turnover managers (value-oriented funds, activist investors) — not diversified index-hugging institutions.

**Required datasets.** SEC 13F filings (free, EDGAR), fund-level historical performance/turnover classification (to separate skilled/low-turnover from noise).

**Public APIs.** SEC EDGAR full-text and structured 13F XML data are fully free; WhaleWisdom and Quiver Quant offer cleaned/aggregated 13F data with free tiers.

**Historical evidence.** 2013-era research found copycat portfolios built from top managers deliver alpha even after the 45-day lag. But Yan & Zhang (2009) found alpha in high-turnover (top-tercile) institutional trades decays completely within roughly twelve months — meaning the type of manager you copy matters enormously; copying a quant/high-turnover fund's 13F is copying noise.

**Statistical significance.** Mixed/manager-dependent — this is a **conditional** anomaly: significant for low-turnover, high-conviction managers; insignificant-to-negative for high-turnover managers, where reported positions may already be stale or reversed by filing date. Average 13F filing lag is ~37 days (std. dev. ~10 days); no evidence managers strategically delay filings to front-run copycats.

**Decay.** Significant decay concentrated in the high-turnover-manager subsample; the low-turnover subsample's edge appears more durable because its underlying alpha source (fundamental research with a multi-quarter holding horizon) doesn't require timeliness to remain valid.

**Implementation difficulty.** Low (data is free and structured) — this is one of the most accessible signals on this list for an individual researcher.

**Possible improvements.** Build a manager-skill classifier (turnover, historical risk-adjusted performance, concentration, activism history) and only copy the top-decile, low-turnover subset; weight by conviction (position size change, not just presence/absence); combine with 13D/13G activist filings (higher-frequency, event-driven, and legally required faster than 13F).

**How institutions already exploit it.** Ironically, "13F alpha" is itself now a commoditized, systematized product (WhaleWisdom, HedgeFollow and similar services sell copycat signals directly to retail and semi-institutional users) — meaning the retail-accessible version of this edge is already crowded.

**Individual edge.** Moderate — genuinely one of the more individual-friendly signals here because the raw data is free, but requires real manager-selection skill/research (not just "copy 13Fs") to avoid the high-turnover-manager trap that the academic literature specifically warns about.

---

### H9. FX Carry Trade / Uncovered Interest Parity (UIP) Violation

**Theory.** Uncovered interest rate parity predicts that high-interest-rate currencies should depreciate enough to offset the rate differential, leaving expected returns equal across currencies. Empirically, UIP is violated ("the forward premium puzzle") — high-rate currencies do not depreciate as much as parity predicts, so borrowing low-rate currencies to fund high-rate currency positions ("carry") earns a positive average excess return. The causal explanation (Brunnermeier, Nagel & Pedersen 2008) is a **crash-risk/liquidity-spiral** story: carry trades are exposed to sudden, correlated unwinds ("currency crashes") when funding liquidity tightens (VIX/TED spread spikes), so the average positive carry return is compensation for a left-tail liquidity-crisis risk, not a free lunch.

**Markets affected.** G10 and EM FX spot/forward markets.

**Securities affected.** Currency pairs/forwards, FX futures, and carry-linked ETFs (e.g., historically CEW, DBV).

**Required datasets.** Spot and forward FX rates, short-term interest rate differentials, VIX, TED spread or equivalent funding-liquidity proxy.

**Public APIs.** FRED (free) for interest-rate and TED-spread-equivalent series; OANDA and Alpha Vantage offer free/cheap historical FX rate APIs; forward rates require a bank/Bloomberg feed for full precision (retail proxies exist via interest-rate-parity-implied calculation, which introduces its own noise).

**Historical evidence.** Extensively documented since Fama (1984) rejected UIP; Brunnermeier, Nagel & Pedersen (2008/2009 NBER) directly link carry-trade returns to crash risk, showing higher VIX/TED spreads predict higher subsequent carry returns (compensation for standing exposure to future crash risk) and that carry-trade *losses* reduce future crash probability but *increase* the market price of crash risk going forward — a genuinely causal, mechanism-level result (liquidity spirals via funding constraints), not just a correlation.

**Statistical significance.** The forward-premium puzzle is one of the most robust anomalies in international finance, replicated across currencies and multi-decade samples; crash-risk linkage findings are significant in the Brunnermeier et al. framework and its many replications.

**Decay.** Persistent — this is a **structural/risk-premium** story (compensation for bearing tail risk), not a behavioral-attention story, so it is theoretically less prone to full arbitrage-away than attention-based anomalies, though the *magnitude* of carry returns has been lower in the post-2008, near-zero-global-rate era simply because interest-rate differentials themselves compressed.

**Implementation difficulty.** Medium. FX carry baskets are straightforward to construct; the hard part is properly modeling and hedging the crash-risk tail (this is precisely where naive carry strategies blow up, as in August 2007 and the 2008 crisis unwind).

**Possible improvements.** Condition position sizing dynamically on VIX/TED-spread level (de-risk carry exposure as funding-liquidity stress rises, rather than static equal-weighting); combine carry with FX momentum and value (PPP-deviation) factors, which have documented low correlation to carry and improve the risk-adjusted profile (this is the core insight behind AQR's and other multi-style FX programs).

**How institutions already exploit it.** Carry is one of the oldest systematized macro strategies; every major macro hedge fund and several mutual-fund complexes run systematic FX carry/multi-style overlays. Highly institutionalized but not eliminated, because the risk (not a behavioral mistake) is the return source — you cannot arbitrage away a genuine risk premium the way you can arbitrage away an attention lag.

**Individual edge.** Moderate. Accessible via FX futures/forwards or currency ETFs with modest capital; the risk premium is real and durable, but individual investors must genuinely accept (and be able to survive) the fat-tailed crash risk — this is not a "free" edge, it is compensated risk-bearing, and sizing discipline matters more than signal discovery here.

---

### H10. Merger Arbitrage Deal-Spread Risk Premium

**Theory.** After a merger is announced, the target's stock trades at a discount to the offer price (the "deal spread"), compensating arbitrageurs for deal-completion risk (regulatory blocks, financing failure, MAC-clause invocation, shareholder rejection). Because this risk is largely idiosyncratic (deal-specific) and diversifiable across many uncorrelated deals, and because dedicated arbitrage capital is limited (specialized due-diligence skill required, per Baker & Savasoglu 2000), the strategy has historically earned a premium return for what is, in a diversified multi-deal portfolio, largely diversifiable risk — a **limits-to-arbitrage** causal story (capital and expertise scarcity), not a pure behavioral one.

**Markets affected.** US and international M&A markets (cash and stock deals).

**Securities affected.** Announced-but-not-closed M&A targets (and, for stock deals, the acquirer as the short leg).

**Required datasets.** M&A deal announcement/completion data (Refinitiv/SDC Platinum institutional standard; SEC merger-proxy (DEFM14A) filings free via EDGAR), daily prices.

**Public APIs.** SEC EDGAR for merger-proxy and 8-K deal-announcement filings (free); no comprehensive free deal-database API exists at SDC Platinum's quality — deal metadata (financing structure, regulatory jurisdiction, MAC clauses) must largely be hand/NLP-extracted from EDGAR filings for a from-scratch build.

**Historical evidence.** Baker & Savasoglu (2000) document significant excess returns to merger arbitrage attributable to limited specialized arbitrage capital; historical completion rate ≈ 90%, median deal spread ≈ 5.9% across ~1,700 observed deals (per aggregated practitioner data); returns are negatively skewed (frequent small gains, occasional large losses on broken deals).

**Statistical significance.** Documented significant risk-adjusted excess returns in the original academic literature, though the strategy's true "alpha" (beyond compensation for the tail risk being taken) is debated — much of the return is arguably a fair risk premium, not a market inefficiency, which matters for how you should think about its persistence.

**Decay.** Zaur Rzakhanov & Gaurav Jetley (2019) document diseconomies of scale — as capital flowed into merger arb post-2008 (many multi-strategy funds and dedicated arb funds scaled up), spreads narrowed, directly showing capacity-driven decay.

**Implementation difficulty.** High. Requires deal-by-deal fundamental judgment (antitrust risk assessment, financing risk, activist-shareholder risk) that resists full quantification — this is one of the harder strategies on this list to fully systematize versus needing genuine judgment overlay.

**Possible improvements.** Use NLP on merger-proxy risk-factor sections and regulatory-filing (HSR, EU merger notification) status to build a systematic completion-probability model rather than relying on judgment alone; the market-implied spread already prices in most public information efficiently (per the "market is efficient" finding that high spreads correlate with high cancellation rates) — so real edge requires a genuinely differentiated information/analytical edge on regulatory outcomes, not just spread-capture.

**How institutions already exploit it.** Heavily — dedicated merger-arbitrage hedge funds are a decades-old, crowded strategy category; the spread narrowing documented by Rzakhanov & Jetley is direct evidence of institutional crowding compressing the premium.

**Individual edge.** Low-moderate. An individual can access the *systematic* beta version cheaply (ETFs like MNA exist), but true alpha requires the deal-diligence judgment that is exactly the scarce input the academic theory says the premium compensates for — hard to replicate without genuine legal/regulatory domain expertise.

---

### H11. Alternative-Data Nowcasting of Fundamentals (Satellite/Credit-Card Panels)

**Theory.** Traditional fundamental data (quarterly filings) is disclosed with a lag and only quarterly; consumer-spending and physical-activity proxies (credit-card transaction panels, satellite imagery of retail parking lots/industrial activity, foot-traffic mobile-location data) allow **nowcasting** of revenue/same-store-sales trends before official disclosure — a data-timeliness arbitrage, not an information-content arbitrage (the information would become public anyway at the earnings date; the edge is purely about being early).

**Markets affected.** US and international retail, consumer discretionary, energy (storage-tank imagery), and industrial (parking-lot/rail-car counting) equities.

**Securities affected.** Retailers, restaurant chains, and commodity storage/shipping operators with physically observable or card-transaction-visible activity.

**Required datasets.** Credit/debit card transaction panels (Yodlee/Envestnet, Facteus, Earnest Research — all paid, and increasingly regulated for consumer-privacy reasons), satellite imagery (Orbital Insight, RS Metrics, Planet Labs — paid), mobile-location foot-traffic data (Placer.ai, SafeGraph — paid, SafeGraph has some free/academic tiers).

**Public APIs.** Essentially no free institutional-grade alt-data source in this category; SafeGraph offers an academic/research tier at reduced cost; Planet Labs offers limited free imagery for research/education use; this hypothesis is the most **data-cost-prohibitive** one in this catalog for an individual researcher.

**Historical evidence.** Berkeley Haas research on satellite retail-parking-lot data finds investors can act on negative retail signals ahead of earnings, generating 4–5% returns within 3 days of trading on the signal; broader industry survey research (2024 J.P. Morgan study cited in trade press) finds hedge funds using alternative data report ~3% higher annual returns than peers not using it (correlational, not necessarily causal — funds sophisticated enough to buy alt data may simply be better funds generally, a confound worth flagging explicitly).

**Statistical significance.** Individual academic studies (e.g., the Berkeley satellite-imagery result) report statistically significant short-window abnormal returns; the broader "alt data helps performance" claim is more a practitioner-survey finding than a rigorously controlled academic result, and should be treated with appropriate skepticism about selection effects.

**Decay.** Fast and well-documented in practitioner literature: "if 300 funds are trading the same satellite signal off the same data, the edge disappears" — signal crowding is now explicitly monitored by data vendors and funds alike; a specific, well-known dataset (e.g., a single popular satellite provider's parking-lot counts) decays within a few years of widespread institutional adoption.

**Implementation difficulty.** Very high, dominated by **cost**, not technical complexity: single alt-data subscriptions run \$25,000–\$150,000+/year for niche panels, pricing out most individual researchers from the highest-quality versions of this signal.

**Possible improvements.** Individual researchers should target the free/cheap edge of this space rather than competing head-on: free satellite tiers (Sentinel-2/Copernicus, USGS Landsat — genuinely free, lower resolution but sufficient for large-scale activity counting with modern computer-vision models), free web-scraped proxies (job postings, product-review velocity — see Part 4 for specific designs), rather than paying for the same commercial panels institutions already crowd.

**How institutions already exploit it.** Extremely heavily — this is the single largest and fastest-growing category of institutional alt-data spend (>\$2.5B allocated industry-wide in 2024, +33% YoY per industry surveys), with dedicated alt-data teams at every major multi-manager platform (Citadel, Point72, Millennium, Balyasny).

**Individual edge.** Low on paid commercial panels (cost-prohibitive and crowded); moderate-to-good on free/low-cost proxies (public satellite tiers + open-source CV, free web-scraped job-posting/app-review data — see Part 4 ideas #2, #7, #22) where institutions' existing paid-vendor relationships mean they rarely bother building bespoke free-data pipelines for niche use cases.

---

### H12. Textual Tone Analysis of Earnings Calls (Loughran-McDonald and Successors)

**Theory.** Managers choose language deliberately, but under real-time Q&A pressure (unscripted, unlike the prepared remarks) they leak information through tone, hedging language, and evasiveness that isn't fully captured by the scripted, legally-vetted prepared statement or by the numerical earnings surprise — a genuine information-leakage causal story distinct from H2's broader PEAD framing, focused specifically on the **unscripted Q&A** portion as the highest-information-density segment.

**Markets affected.** US, and increasingly international, equities with earnings-call transcripts (large/mid-cap primarily, where calls are held and transcribed).

**Securities affected.** Common equities across sectors; effect concentrated around and shortly after the call date.

**Required datasets.** Earnings-call transcripts split into prepared-remarks vs. Q&A sections, Loughran-McDonald financial sentiment dictionary (free, academic), CRSP/Compustat returns.

**Public APIs.** No comprehensive free transcript API (see H2); Loughran-McDonald dictionary itself is freely downloadable from University of Notre Dame's site for word-list-based scoring; modern approach would substitute an LLM-based zero-shot/few-shot classifier for the legacy bag-of-words dictionary.

**Historical evidence.** Multiple studies (surveyed in the ScienceDirect literature on conference-call tone) find call discussion tone has significant incremental explanatory power for both the immediate announcement-window return and the subsequent PEAD drift window, and that tone predicts the *drift* component better than the numeric surprise alone does.

**Statistical significance.** Reported as highly significant in the original Loughran-McDonald-derived literature and its many extensions; effect sizes vary by study/sample but are consistently statistically distinguishable from zero after controlling for the numeric surprise.

**Decay.** Likely partially decayed for the most obvious dictionary-based signals (Loughran-McDonald word lists are two decades old, widely known, and easy to replicate — any fund with a data-science team runs this) but the frontier has moved to LLM-based semantic/tone extraction (detecting evasiveness, hedging, and non-answer patterns in Q&A specifically), which is less commoditized.

**Implementation difficulty.** Medium (dictionary-based) to high (LLM-based semantic extraction, which requires careful prompt/model validation to avoid look-ahead bias from using a model trained on data that post-dates your backtest period — a genuinely tricky point-in-time modeling issue specific to LLM-based signals, addressed further in Part 3).

**Possible improvements.** Focus specifically on **CEO/CFO answer evasiveness** in the Q&A (e.g., measuring topic drift between analyst question and executive answer via embedding similarity, or answer length/hedging-word density relative to that executive's own historical baseline) rather than generic positive/negative sentiment, which is largely commoditized; use a fixed, frozen model version matched to the backtest period to avoid data leakage.

**How institutions already exploit it.** Standard tooling now at any systematic fund with an NLP capability; several vendors (AlphaSense, Bloomberg's own NLP tools, Amenity Analytics) sell pre-built transcript-sentiment feeds directly to buy-side desks.

**Individual edge.** Low on generic dictionary-based sentiment (fully commoditized, free dictionary, trivial to replicate — meaning everyone already has). Moderate on genuinely novel semantic features (evasiveness-in-Q&A, cross-quarter linguistic-consistency drift for the same executive) that require real NLP engineering effort most retail researchers won't invest in but that a technically capable individual can build.

---

### H13. Investor Attention via Search Volume (Da-Engelberg-Gao and Extensions)

**Theory.** Retail-investor attention is a scarce resource; spikes in Google search volume for a ticker (distinct from news coverage or trading volume, which conflate informed and uninformed activity) proxy specifically for *retail* attention. Da, Engelberg & Gao (2011) argue attention-driven buying by uninformed investors creates temporary price pressure that partially reverses — a behavioral overreaction/reversal story, causally linked to a specific, measurable attention shock rather than a vague "sentiment" concept.

**Markets affected.** US equities, especially small/mid-cap names where retail participation is a larger share of volume; also documented in IPO pricing.

**Securities affected.** Russell 3000 constituents in the original study; effect concentrated in smaller, less-institutionally-dominated names and IPOs.

**Required datasets.** Google Trends Search Volume Index (SVI), daily prices/volume.

**Public APIs.** Google Trends has no official public API but the `pytrends` unofficial Python library is widely used (rate-limited, unofficial, ToS-gray-area — flag this explicitly to the user as a fragility point for any production pipeline); Wikipedia's official Pageviews API (genuinely free, official, stable) is a good, more robust substitute/complement, per H-idea in Part 4.

**Historical evidence.** Da, Engelberg & Gao (2011, *Journal of Finance*): SVI increases predict higher prices over the following 2 weeks, followed by a price reversal within the year; SVI also contributes to explaining first-day IPO overpricing and long-run IPO underperformance.

**Statistical significance.** Original paper reports statistically significant predictability, widely replicated in subsequent literature across markets (a 2023 systematic review in *Financial Innovation* surveys the now-large replication literature).

**Decay.** Plausibly decayed for the raw, single-ticker SVI signal given wide institutional and retail-platform (e.g., some brokerages already surface trending-search data to users) adoption since 2011, though the general "attention proxy" research direction remains academically active — the specific implementation (Google Trends on ticker names) is the most commoditized version; newer, less-crowded attention proxies (Wikipedia edit velocity, Reddit/forum post velocity via free APIs) are less thoroughly arbitraged.

**Implementation difficulty.** Low (Google Trends/pytrends is simple to query) but fragile (unofficial API, rate limits, data revisions on re-query — Google Trends values are relative/normalized and can shift retroactively, a genuine look-ahead-bias trap if you don't snapshot data at the time of use).

**Possible improvements.** Combine attention *level* with attention *acceleration* (2nd derivative) rather than level alone; use Wikipedia pageviews (official, stable, free, timestamped precisely) as a more research-robust substitute or complement to Google Trends; separate attention shocks that co-occur with news (likely already informationally efficient) from attention shocks with no identifiable news trigger (more likely pure noise-trader activity, closer to the theoretical mechanism).

**How institutions already exploit it.** Widely known and taught in every quant-finance graduate program at this point; several alt-data vendors package attention/sentiment indices commercially; the core idea is not proprietary to any fund.

**Individual edge.** Low on the vanilla implementation (extremely well known, free data, trivially replicable — thousands of quant-finance students have run this exact backtest). Worthwhile mainly as a **feature** within a larger ensemble (Part 3) rather than a standalone strategy, and as a base case for testing genuinely novel attention proxies (Part 4 ideas #13, #29) that haven't been through a decade of academic replication yet.

---

### H14. Environmental/Biological Mood Anomalies (Geomagnetic Storms, Daylight Saving, SAD) — a Low-Conviction, High-Caution Inclusion

**Theory.** A cluster of papers (Kamstra, Kramer & Levi 2000/2003; Krivelyova & Robotti 2003; Dichev & Janes 2003; Yuan, Zheng & Zhu 2006) propose that exogenous physiological/environmental factors — geomagnetic storm activity, daylight-saving-time sleep disruption, seasonal reduction in daylight (Seasonal Affective Disorder), and lunar phase — shift aggregate investor mood and risk aversion, producing small but statistically detectable return patterns. The proposed causal chain (environmental factor → mood/sleep disruption → risk aversion → required-return shift → price) is genuinely mechanistic, not just a labeled correlation, which is why it's included despite low economic magnitude.

**Markets affected.** Global equity indices (studies span US, and international comparisons exploiting Southern/Northern hemisphere daylight asymmetry for SAD, and country-level geomagnetic-latitude variation for storm effects).

**Securities affected.** Broad market indices (these are aggregate-sentiment stories, not stock-specific, so they apply best to index/ETF-level strategies, not single-name selection).

**Required datasets.** NOAA geomagnetic activity (Ap/Kp index), daylight-saving transition dates by country, sunrise/sunset hours by latitude, lunar calendar, index-level daily returns.

**Public APIs.** NOAA Space Weather Prediction Center API (genuinely free, official) for geomagnetic data; all other inputs (DST dates, sunrise/sunset, lunar phase) are trivially computable/free (`astral`, `ephem` Python libraries).

**Historical evidence.** Each sub-effect (DST, SAD, lunar, geomagnetic) has multiple published, peer-reviewed findings of statistically significant average return differences on the relevant days/periods, replicated across several international samples per the search results (Kamstra et al.'s SAD/DST work published in top journals including *American Economic Review*).

**Statistical significance.** Individually significant in the original studies, but **economically tiny** (effect sizes are typically a few basis points per relevant period) and this entire literature is a textbook target for the Harvey-Liu-Zhu multiple-testing critique (Part 3) — with hundreds of possible calendar/environmental variables tested across decades of research, some will appear significant by chance, and the *ex-post* selection of "which anomaly to publish" is itself a data-mining process that inflates apparent significance versus a true out-of-sample test.

**Decay.** Unclear/unresolved — because effect sizes are so small relative to transaction costs, it's genuinely hard to distinguish "decayed" from "was mostly noise/multiple-testing artifact to begin with." This is the single most appropriate hypothesis in this catalog to run through the full Part 3 pipeline (proper multiple-hypothesis correction, walk-forward validation) before concluding anything.

**Implementation difficulty.** Low data/engineering difficulty; high difficulty in achieving genuine statistical rigor (this category is a minefield for false positives).

**Possible improvements.** Treat all such variables as candidate features in a regularized, multiple-testing-corrected ensemble (Part 3) rather than testing each in isolation with a naive t-test; require effect sizes to clear a materially higher significance bar (Harvey-Liu-Zhu's t > 3.0 recommendation, ideally combined with a Bonferroni/Benjamini-Hochberg correction across the full family of environmental variables tested) before treating any of these as real.

**How institutions already exploit it.** Essentially not exploited as standalone strategies by any credible institutional desk (transaction costs dwarf the effect sizes); the literature is cited mainly in academic behavioral-finance and market-efficiency debates, not as a practitioner playbook.

**Individual edge.** Effectively none as a tradeable standalone strategy net of transaction costs. Included specifically as **methodological pedagogy**: it demonstrates why "statistically significant in one published paper" is an insufficient bar, and why Part 3's multiple-testing-correction and walk-forward infrastructure matters — build the discipline on a case where you can be confident the true effect, if any, is close to the noise floor.

---

## PART 2 — RANKING MATRIX

Scored 1 (worst) – 5 (best) for Expected Alpha, Novelty, and Scalability; 1 (worst) – 5 (best) for Implementation *Ease* (so higher = easier, i.e., lower difficulty); Data Cost and Competition scored 1 (worst, i.e., expensive/highly competitive) – 5 (best, i.e., cheap/low-competition). This orientation means **higher is always better** across every column, so the composite is a simple mean.

| # | Hypothesis | Expected Alpha | Implementation Ease | Data Cost (5=cheap) | Competition (5=low) | Novelty | Scalability | Composite |
|---|---|---|---|---|---|---|---|---|
| H1 | Supplier-customer momentum | 2 | 3 | 3 | 2 | 2 | 2 | 2.33 |
| H2 | PEAD (text-augmented) | 3 | 3 | 3 | 2 | 3 | 3 | 2.83 |
| H3 | Index reconstitution | 1 | 4 | 3 | 1 | 1 | 2 | 2.00 |
| H4 | Options IV skew/spread | 3 | 2 | 2 | 2 | 3 | 3 | 2.50 |
| H5 | Dealer gamma exposure (GEX) | 2 | 3 | 2 | 2 | 3 | 3 | 2.50 |
| H6 | VPIN order-flow toxicity | 1 | 1 | 1 | 2 | 1 | 2 | 1.33 |
| H7 | Short interest / lending fee | 3 | 3 | 2 | 2 | 2 | 2 | 2.33 |
| H8 | 13F herding/copycat | 2 | 5 | 5 | 2 | 2 | 2 | 3.00 |
| H9 | FX carry / UIP violation | 3 | 4 | 4 | 2 | 1 | 5 | 3.17 |
| H10 | Merger arbitrage spread | 3 | 2 | 3 | 2 | 2 | 3 | 2.50 |
| H11 | Alt-data nowcasting (sat/CC) | 4 | 1 | 1 | 2 | 3 | 2 | 2.17 |
| H12 | Earnings-call tone (LLM) | 3 | 2 | 3 | 3 | 4 | 3 | 3.00 |
| H13 | Search-volume attention | 1 | 5 | 4 | 1 | 1 | 3 | 2.50 |
| H14 | Environmental/mood anomalies | 1 | 4 | 5 | 5 | 2 | 4 | 3.50 (alpha net of cost ≈ 0) |

**How to read this table.** H14 scores well on the mechanical dimensions (cheap, easy, low-competition because nobody bothers) precisely *because* nobody thinks the alpha is real net of costs — a high composite here is not a recommendation, it reflects that the "cost" columns are structurally favorable even though Expected Alpha is 1. Composite scores should never be read without the Expected Alpha column alongside them. The genuinely most actionable cells for an individual researcher, weighting Expected Alpha and Scalability-per-dollar-of-data-cost most heavily, are **H12** (novel NLP angle, moderate cost, real edge if you do the engineering) and **H9** (durable structural premium, accessible instruments, real tail risk to manage) — followed by **H8** (free data, genuine if narrow edge with correct manager selection) and **H7** (real signal, but paid data materially improves it).

---

## PART 3 — AUTOMATED RESEARCH DISCOVERY PIPELINE

The objective here is a system that continuously *generates and tests* candidate relationships under proper statistical discipline, rather than a human manually backtesting one idea at a time. This design follows the methodological framework established by López de Prado (*Advances in Financial Machine Learning*, 2018) combined with the Harvey-Liu-Zhu multiple-testing correction and modern MLOps practice.

### 3.1 Architecture overview

```
[Point-in-time data lake] 
        │
        ▼
[Feature Generation Engine] ──► [Feature Store (versioned, PIT-stamped)]
        │
        ▼
[Automated Feature Selection] ──► [Candidate Signal Registry]
        │
        ▼
[Purged/Embargoed Time-Series CV] ──► [Walk-Forward Validation Harness]
        │
        ▼
[Multiple Hypothesis Correction Layer] ──► [Surviving Signals]
        │
        ▼
[Regime Detection] ──► [Regime-Conditional Model Routing]
        │
        ▼
[Bayesian Updating / Hierarchical Shrinkage] ──► [Posterior Signal Weights]
        │
        ▼
[Ensemble Construction (stacking/meta-labeling)] ──► [Explainability Layer (SHAP/causal DAG audit)]
        │
        ▼
[Portfolio Construction + Risk Overlay] ──► [Paper-Trading Shadow Book] ──► [Live Capital]
```

### 3.2 Feature generation

- **Structured-data feature synthesis**: automated deep feature synthesis (DFS)-style generation of ratios, cross-sectional ranks, rolling-window transforms (z-scores, momentum, mean-reversion residuals), and interaction terms across fundamental, price, and alt-data tables. Tools: `featuretools`, or a custom genetic-programming feature generator (`gplearn`) that evolves nonlinear combinations of primitives and is scored directly against forward returns with fitness penalized for complexity (to control overfitting at the generation stage, not just at selection).
- **Unstructured-data feature extraction**: transformer-embedding pipelines (open-weight financial-domain models, e.g., FinBERT-family, or general-purpose LLM embeddings) applied to filings/transcripts/news, reduced via PCA/UMAP to a manageable factor count before entering the feature store — raw high-dimensional embeddings should never go directly into a cross-sectional regression without dimensionality control.
- **Cross-domain features**: explicitly generate interaction features across the hypothesis families above (e.g., H4 × H7: options-skew-signal × short-interest-signal, since the underlying informed-trading theory predicts these should interact, not just add).
- **PIT-stamping discipline**: every feature must be stored with (a) the timestamp the underlying data became *publicly knowable* (not the period it describes — a Q1 10-Q "as of" date is not when it was filed), and (b) a version hash of any model (e.g., LLM) used to derive it, since model updates change historical feature values if regenerated later — this second point is a genuinely underappreciated look-ahead-bias vector unique to LLM-derived features.

### 3.3 Automated feature selection

- **Stage 1 — cheap filters**: mutual information and Spearman rank-IC screening against forward returns, computed *only* within each walk-forward training fold (never on the full sample) to avoid selection-driven look-ahead bias.
- **Stage 2 — regularized selection**: elastic-net / LASSO logistic or linear models across the surviving feature set, with time-series-aware cross-validation (3.4) for hyperparameter tuning.
- **Stage 3 — model-based importance**: gradient-boosted trees (XGBoost/LightGBM/CatBoost) trained per fold, feature importance via SHAP values (not naive gain/split-count importance, which is biased toward high-cardinality features) aggregated across folds; a feature must show *stable-sign, stable-magnitude* importance across a majority of folds to survive — instability across folds is itself diagnostic of overfitting or regime-dependence.
- **Stage 4 — orthogonalization**: residualize surviving features against known risk factors (Fama-French-Carhart-Q5, plus your own previously-validated signals) so the pipeline reports genuinely *incremental* alpha, not repackaged exposure to a known factor.

### 3.4 Time-series validation: purged, embargoed k-fold

Standard k-fold CV is invalid for financial time series because (a) observations are serially correlated (a feature computed on overlapping return windows leaks information across the fold boundary) and (b) label horizons overlap in time. Use **Purged K-Fold Cross-Validation with Embargo** (López de Prado):
1. Split the timeline into k contiguous folds.
2. For each test fold, **purge** any training observation whose label window overlaps the test fold's time span (removes the direct overlap leak).
3. Apply an **embargo** period after each test fold (e.g., a number of days equal to the longest feature lookback or label horizon used) during which adjacent training observations are also excluded (removes indirect leak from serial correlation/autocorrelation bleeding across the boundary).
4. For strategies with meaningfully different regimes, use **Combinatorial Purged Cross-Validation (CPCV)** — generate all combinations of train/test fold groupings (not just k sequential splits) to produce a distribution of out-of-sample Sharpe ratios rather than a single point estimate, which directly supports the deflated-Sharpe correction in 3.6.

### 3.5 Walk-forward testing

- **Anchored walk-forward**: expanding training window, fixed-length out-of-sample test window, re-fit at each step (simulates realistic "train on everything known so far" deployment).
- **Rolling walk-forward**: fixed-length training window that slides forward (tests robustness to regime change / non-stationarity, since it discards old data rather than accumulating it — compare anchored vs. rolling performance degradation as a direct regime-stability diagnostic).
- **Reoptimization schedule**: hyperparameters and feature-selection results should be refreshed on a realistic cadence (e.g., quarterly) — never tune once on the full historical sample and apply statically; log every reoptimization event and its resulting parameter set for post-hoc audit of parameter stability over time (frequent large parameter swings across reoptimizations is itself a red flag for overfitting).
- **Cost and capacity modeling inside the walk-forward loop, not after it**: apply realistic transaction-cost, market-impact (square-root model calibrated to average daily volume), and borrow-cost assumptions *within* each walk-forward step, so reported performance already reflects implementation frictions rather than requiring a separate, easily-fudged "haircut" applied after the fact.

### 3.6 Multiple hypothesis correction

Given automated feature generation will produce thousands of candidate signals, naive t > 2 significance testing guarantees a large fraction of false discoveries.
- **Harvey-Liu-Zhu framework**: apply their dynamic significance-threshold model (recommends t > 3.0 for newly "discovered" factors as of their most recent calibration, accounting for the cumulative number of factors tested in the literature to date) as a floor, and additionally track your *own* pipeline's cumulative test count separately, since your internal multiple-testing burden compounds independently of the published-literature burden they model.
- **False Discovery Rate control**: Benjamini-Hochberg procedure across the full batch of candidate signals tested in a given research cycle, rather than Bonferroni (too conservative given correlated features) or uncorrected p-values (too liberal).
- **Deflated Sharpe Ratio (DSR)**: Bailey & López de Prado's DSR statistic explicitly penalizes the reported Sharpe ratio by the number of trials run and the skewness/kurtosis of the returns distribution — every candidate signal's headline Sharpe should be reported alongside its DSR, and only DSR-significant signals proceed to ensemble construction.
- **Reality Check / SPA test**: White's Reality Check or Hansen's Superior Predictive Ability test as a final gate, benchmarking the *best* discovered strategy against a null of "best of many random strategies," which directly answers the question "could I have gotten a result this good by chance alone given how many things I tried."

### 3.7 Avoiding look-ahead bias

- Point-in-time (PIT) fundamental data (Compustat Point-in-Time, or your own EDGAR-derived PIT dataset built from original filing timestamps, not restated/as-reported-today values).
- Earnings/economic data release-time stamping (many free data providers silently backfill "as-known-today" values — verify vendor methodology explicitly; this is one of the most common silent errors in retail-grade backtests).
- LLM-derived features must use a model version whose training-data cutoff *predates* the historical period being scored, or must be explicitly flagged as using look-ahead information (an LLM trained through 2026 "knows" about a 2015 company's eventual fate in a way no contemporaneous investor did) — for genuinely rigorous backtesting of LLM-based signals, either use models with clearly documented, period-appropriate cutoffs, or run a leakage-sensitivity test comparing signal performance immediately after vs. long after the model's training cutoff.
- Corporate-action and universe-membership data must reflect what was knowable at each historical rebalance date (ticker changes, splits, delistings applied point-in-time, not retroactively).

### 3.8 Avoiding survivorship bias

- Use a data vendor/dataset that includes delisted securities with accurate delisting returns (CRSP is the academic gold standard; several commercial vendors silently drop delisted names, which biases backtested universes toward survivors and inflates apparent returns).
- Reconstruct historical index/universe membership point-in-time (e.g., the Russell 2000 membership on a given historical date, not today's membership applied retroactively) — this matters enormously for anomalies like H3 that are defined relative to index membership.
- Explicitly model delisting-return assumptions for bankruptcies/acquisitions (CRSP's delisting-return imputation methodology is a reasonable default; using a naive "drop the observation" approach materially overstates historical returns because delistings are disproportionately negative events).

### 3.9 Regime detection

- **Hidden Markov Models** on a small set of macro/market-state variables (realized volatility, term-spread, credit-spread, cross-asset correlation) to classify latent regimes (e.g., risk-on/risk-off, high-vol/low-vol, trending/mean-reverting).
- **Bayesian online changepoint detection** for real-time regime-shift flagging without needing to pre-specify the number of regimes.
- **Regime-conditional model routing**: rather than a single global model, maintain regime-specific model weights/parameters (e.g., H5's GEX signal should be weighted differently in a low-vol grinding-up regime vs. a post-crash high-vol regime) and route live signals through the currently-detected regime's model — validate this routing itself out-of-sample (a regime classifier that's only accurate in-sample is another overfitting vector).

### 3.10 Bayesian updating

- **Hierarchical Bayesian shrinkage** of individual signal Sharpe-ratio/IC estimates toward a cross-sectional prior (e.g., shrink each of your 44 candidate signals' estimated IC toward the grand-mean IC across all signals, with shrinkage intensity inversely proportional to each signal's estimation-sample size) — this directly addresses the "many small, noisy estimates" problem inherent in a large automated-discovery pipeline, and is a principled alternative to hard multiple-testing cutoffs.
- **Sequential Bayesian updating** of signal-weight posteriors as new out-of-sample data arrives (rather than static walk-forward refits), using a Kalman-filter or particle-filter framework for continuously time-varying factor exposures.
- **Bayesian model averaging** across the ensemble's candidate specifications, weighting by posterior model probability rather than committing to a single "winning" model specification, which is itself a form of protection against overfitting to one particular specification choice.

### 3.11 Explainable AI

- **SHAP (SHapley Additive exPlanations)** values computed per-prediction and aggregated, to attribute each model's forecast to specific input features — critical for distinguishing genuine causal-adjacent signals from spurious ones that happen to correlate in-sample.
- **Partial dependence / accumulated local effects (ALE) plots** for each surviving feature to sanity-check monotonicity and economic plausibility (a feature whose SHAP-implied relationship contradicts basic economic reasoning, e.g., higher short interest → *higher* future returns with no plausible mechanism, should trigger manual review rather than automatic inclusion).
- **Causal DAG auditing**: for every surviving signal, explicitly draw the proposed causal graph (as done in Part 1's "Theory" sections) and check whether the SHAP-implied relationship is consistent with the hypothesized causal direction, not just an unexplained correlation — this is the operationalization of your original requirement to "focus on causal relationships rather than correlations."
- **Counterfactual analysis**: for a sample of predictions, perturb individual features and observe forecast changes to validate that the model is using features in economically sensible ways rather than exploiting spurious high-dimensional interactions.

### 3.12 Ensemble models

- **Stacking**: train a diverse base-model layer (regularized linear, gradient-boosted trees, a shallow neural network, and a regime-specific model per 3.9) on the purged/embargoed folds, then train a meta-learner (typically a simple regularized linear model, to avoid re-introducing overfitting at the meta-level) on the out-of-fold base-model predictions.
- **Meta-labeling (López de Prado)**: use a primary model to generate a directional signal, then train a *secondary* model whose job is solely to predict whether the primary signal will be correct (sized as a bet-sizing/confidence filter) — this decomposes "should I trade" from "which direction," which materially improves precision without touching the underlying signal-generation logic.
- **Diversity-weighted ensembling**: weight base models not just by individual accuracy but by their prediction-correlation with the rest of the ensemble (favor low-correlation, moderately-accurate models over a high-correlation cluster of similarly-accurate models) to maximize the ensemble's effective diversification.
- **Ensemble-level walk-forward re-validation**: the full ensemble (not just individual base models) must itself pass the walk-forward and multiple-testing gates in 3.5–3.6 — an ensemble of individually-validated signals is not automatically itself validated, since the stacking/meta-learning step introduces its own overfitting risk.

---

## PART 4 — 30 ORIGINAL RESEARCH IDEAS (with exact backtest specifications)

Each idea below is intentionally outside the mainstream retail/academic-101 canon. Format: **Theory → Data → Signal → Backtest → Key pitfall.**

**1. Corporate-jet flight-pattern M&A nowcasting.**
Theory: pre-announcement due-diligence requires executives/bankers/lawyers to physically visit target HQ or advisor offices; private-jet tail numbers registered to acquirers or known advisory firms show anomalous flight-frequency spikes to a target's home airport before deal announcement.
Data: ADS-B Exchange or FlightAware AeroAPI (tail-number-level historical flight logs, free/low-cost tiers), FAA aircraft registry (tail number → owner, free), M&A announcement dates (SEC EDGAR).
Signal: for each known corporate-jet tail number, compute rolling 30-day flight-frequency z-score to airports within a defined radius of candidate target headquarters; flag anomalies (z > 2) as pre-announcement candidates.
Backtest: retrospectively pull flight logs for tail numbers of confirmed acquirers in the 90 days pre-announcement across a sample of ≥200 historical deals (2015–2025, deal data from EDGAR merger proxies); test whether flight-frequency anomalies cluster in the 5–30 day pre-announcement window versus a matched placebo sample of non-deal periods for the same aircraft; event-study CAR around a simulated "buy the target on anomaly-flag date" rule versus buying on the actual announcement date, net of a realistic false-positive rate (most flight anomalies won't precede an actual deal).
Pitfall: extremely low signal-to-noise (executives fly for countless non-M&A reasons); ADS-B coverage gaps for aircraft using anonymization (ADS-B "PIA" privacy program), which is disproportionately used by exactly the sophisticated acquirers you're trying to track.

**2. Job-posting velocity as an earnings-miss leading indicator.**
Theory: hiring-freeze or headcount-reduction decisions precede formal earnings guidance cuts by 1–2 quarters, and are visible in job-posting-board activity before being disclosed.
Data: Indeed/LinkedIn job-posting counts by employer (scraped or via aggregator APIs like Revelio Labs, which has some research-tier access), historical earnings-guidance data (I/B/E/S).
Signal: rolling 90-day job-posting-count growth rate per employer relative to its own trailing-12-month baseline and relative to sector-median growth.
Backtest: universe of Russell 3000 constituents 2018–2025; regress next-quarter earnings-surprise sign/magnitude on the job-posting-growth signal, controlling for sector and prior-quarter earnings surprise (to isolate incremental information); construct a long/short decile portfolio (long top job-posting-growth decile, short bottom) rebalanced monthly, evaluate Fama-French-Carhart-5 alpha and t-stat via Newey-West standard errors (to correct for overlapping-window autocorrelation).
Pitfall: job postings are a noisy, gameable proxy (postings can be "evergreen"/never actually filled); scraping ToS risk from job boards; survivorship bias if the data vendor only backfills currently-active companies.

**3. Patent-citation-network centrality shift as long-run R&D-productivity predictor.**
Theory: a firm's position in the patent-citation graph (how central/bridging its patents are within the technology-citation network) predicts future innovation productivity and, with a multi-year lag, stock returns, because network centrality is observable years before it shows up in reported R&D-output metrics like revenue growth.
Data: USPTO PatentsView API (free, comprehensive), Compustat for financials.
Signal: eigenvector/betweenness centrality of each firm's patent portfolio within a rolling 5-year citation graph, computed annually.
Backtest: universe of US-listed firms with ≥20 patents in a given rolling window, 2000–2020 (leaving a 2020–2025 genuine out-of-sample holdout); sort into centrality quintiles annually, form value-weighted portfolios held for 3-year forward windows (matching the theorized multi-year lag), test against the Fama-French-Q5 model plus an explicit R&D/market-cap control (since centrality could just proxy for R&D intensity, which needs to be residualized out to claim incremental information).
Pitfall: patent-citation lags (a citing patent can take 2+ years to be granted and appear in the data) create a genuine PIT-construction challenge — must use patent *application* dates with an appropriate reporting lag, not grant dates, to avoid look-ahead bias.

**4. Utility-filing-based data-center power draw as hyperscaler capex nowcast.**
Theory: large cloud/AI data-center buildouts require utility interconnection agreements and power-purchase filings that are public record at state utility commissions, months before the capex shows up in quarterly filings.
Data: state Public Utility Commission (PUC) dockets (mostly free, state-by-state, inconsistent formats — a genuine data-engineering project), EIA API (aggregate regional power-demand data, free).
Signal: count and aggregate megawatt-capacity of new large-load interconnection filings by known hyperscaler-affiliated shell/subsidiary entity names, by state/quarter.
Backtest: hand-map hyperscaler shell-entity names to parent companies (Amazon/AWS, Microsoft, Google, Meta subsidiaries commonly use opaque LLC names — this mapping is itself a valuable proprietary dataset once built) for 2018–2025; regress next-2-quarter capex-guidance revisions and semiconductor-supplier (NVDA, AVGO, power-infrastructure names like VRT, ETN) revenue surprises on the lagged interconnection-filing signal; event-study around large filing clusters.
Pitfall: filing-to-construction-to-power-draw lag is long and variable (regulatory approval alone can take 1–3 years), diluting the timeliness advantage; entity-name mapping requires ongoing manual maintenance as new shell names appear.

**5. Customs bill-of-lading data for company-specific inventory-writedown prediction.**
Theory: import volume/composition changes visible in US customs bill-of-lading records (public record) predict inventory build-up or destocking 1–2 quarters before it appears in reported gross-margin/inventory-turnover figures.
Data: US Customs import manifest data (public record; commercial aggregators like ImportGenius/Panjiva repackage it, paid, but the underlying data is technically public and can be obtained more cheaply via FOIA-adjacent bulk-data resellers).
Signal: rolling company-level (mapped via known consignee names) import-volume growth versus same-company trailing-sales growth — a widening gap (imports growing faster than sales) flags inventory-buildup/writedown risk.
Backtest: retailer/consumer-goods universe with identifiable US-importer-of-record names, 2015–2024; regress next-quarter gross-margin surprise on the import-sales-growth-gap signal, controlling for sector and prior gross margin trend; portfolio sort (long low-gap/lean-inventory names, short high-gap/bloated-inventory names).
Pitfall: consignee-name-to-public-company mapping is genuinely hard (many companies import via third-party logistics providers whose name appears on the manifest instead of the actual retailer); doesn't capture non-ocean-freight imports (air freight, which matters disproportionately for high-value/rush goods).

**6. SEC comment-letter linguistic analysis for restatement-risk prediction.**
Theory: SEC staff comment letters (a formal review/challenge process on filings, publicly released with a lag) contain accounting-quality red flags that predict future restatement risk before it's realized; the tone/specificity/persistence (multiple rounds of back-and-forth) of the correspondence is informative beyond the mere existence of a comment letter.
Data: SEC EDGAR full-text search (comment letters are released ~20 days after resolution, structurally lagged but still ahead of any eventual restatement), restatement databases (Audit Analytics — paid; can proxy with 8-K Item 4.02 "non-reliance" filings, free via EDGAR).
Signal: NLP classification of comment-letter severity/topic (revenue recognition, going-concern, related-party — historically higher-restatement-risk categories) and round-count (number of SEC follow-up letters before resolution).
Backtest: universe of all companies receiving SEC comment letters 2005–2023 (EDGAR full-text searchable); logistic regression of subsequent-24-month restatement (8-K Item 4.02) on comment-letter features, controlling for company size/sector/auditor; compare AUC of NLP-feature model versus a naive "any comment letter" baseline to isolate the incremental value of the linguistic analysis specifically.
Pitfall: comment letters are released with an inherent ~20-day-to-multi-month lag and only after SEC-company correspondence concludes, meaning the true "informative" window may already be substantially closed by public release; base rate of restatements is low (class imbalance requires careful backtest design, e.g., precision-recall rather than accuracy as the primary metric).

**7. App-store review velocity and ranking-change signal for subscription-revenue nowcasting.**
Theory: consumer app companies' subscription revenue trends are visible in app-store ranking changes and review-velocity/sentiment shifts weeks before quarterly disclosure.
Data: App Store/Google Play category-ranking history (data.ai/Sensor Tower — paid, but App Store rankings themselves are scrapeable at low volume for research use, ToS caveats apply) or SimilarWeb API (has a free tier for limited queries).
Signal: rolling category-rank change and review-count growth rate per app, mapped to parent public company.
Backtest: universe of public companies with a flagship consumer app (dating, fitness, fintech, gaming — 2018–2025); regress next-quarter revenue surprise on lagged rank-change/review-velocity signal, controlling for sector and seasonality (app usage is seasonal, e.g., fitness apps spike in January); long/short portfolio on the signal, evaluated with Newey-West-adjusted t-stats given overlapping quarterly windows.
Pitfall: single-app signal may be a small fraction of a diversified company's total revenue (materiality varies enormously by company, must be explicitly weighted/filtered); ranking algorithms themselves change over time (a platform-algorithm change can look like a company-specific signal shift and must be differenced out via category-relative, not absolute, ranking).

**8. Employee-review sentiment cross-confirmed with options skew (dual-signal convergence).**
Theory: employee-review-platform (Glassdoor/Blind) sentiment deterioration is a known, already-somewhat-crowded leading indicator of guidance cuts; a genuinely novel angle is testing whether the signal's reliability is meaningfully higher when it's *cross-confirmed* by options-market skew steepening (H4) around the same window, versus firms where only one signal fires — i.e., testing the interaction, not either signal alone.
Data: Glassdoor/Blind review timestamps and ratings (scraped, ToS-restricted — flag clearly), OptionMetrics/ORATS IV-skew data.
Signal: binary interaction flag = 1 when both (a) rolling-90-day Glassdoor rating z-score < −1.5 and (b) OTM put skew z-score > 1.5 occur within the same 30-day window.
Backtest: universe with both data types available (large/mid-cap, optionable, sufficient Glassdoor review volume), 2015–2024; compare forward 60-day returns and earnings-surprise outcomes for the interaction-flagged group versus each single-signal group and a no-signal control group; test whether the interaction effect is statistically distinguishable from the sum of the two individual effects (a formal interaction-term regression, not just a subgroup comparison) to establish genuine complementarity rather than redundancy.
Pitfall: review-platform scraping is fragile and ToS-restricted (build with an awareness this may require a paid data partnership for production use); small sample size in the dual-confirmation bucket reduces statistical power, a real constraint given this is deliberately a narrower, rarer-triggering signal.

**9. State-legislature bill-text tracking for pre-mainstream-coverage regulatory-shock pricing.**
Theory: state-level legislative bills (before federal attention or mainstream financial-media coverage) can be an early, machine-readable leading indicator of sector-specific regulatory risk (e.g., a wave of state PBM-reform bills preceding federal pharmacy-benefit-manager scrutiny, or state AI-liability bills preceding tech-sector regulatory repricing).
Data: LegiScan API (free, comprehensive US state-legislature bill-tracking, genuinely excellent low-cost dataset for this purpose), sector-mapping of affected public companies.
Signal: rolling count of newly-introduced, sector-relevant bills (keyword/topic-classified, ideally via an LLM classifier rather than rigid keyword-matching given bill-text heterogeneity) across all 50 states, weighted by bill progression stage (introduced < committee-passed < floor-passed).
Backtest: choose 3–4 historical regulatory-shock episodes with identifiable affected sectors (e.g., 2021–2023 PBM reform, 2023–2025 state AI-liability legislation) as case studies; construct the bill-momentum signal with a strict PIT cutoff and test whether it Granger-causes (in a formal Granger-causality test, not just visual inspection) subsequent sector-ETF or affected-stock abnormal returns/implied-volatility increases, with the case-study design explicitly disclosed as lower-power than a large cross-sectional backtest given the necessarily small number of clean historical "regulatory wave" episodes.
Pitfall: genuinely small sample of clean historical episodes (this is closer to an event-study/case-study methodology than a large-N cross-sectional backtest, and should be presented with that caveat); topic classification of heterogeneous bill text is a real NLP-engineering challenge, not a trivial keyword match.

**10. UN Comtrade-based supply-chain reshoring detector.**
Theory: bilateral trade-flow data reveals manufacturing reshoring/friend-shoring trends (e.g., a category shifting from China-origin to Mexico/Vietnam-origin) months before it's discussed in earnings calls, with direct margin implications for companies exposed to the shifting supply chain.
Data: UN Comtrade API (free, monthly-lagged bilateral trade-flow data by product code).
Signal: rolling year-over-year share-of-origin-country change for HS product codes relevant to a given sector (e.g., semiconductors, apparel, EV batteries), as a sector-level (not firm-specific, a real limitation) leading indicator of supply-chain-transition-related cost/margin pressure.
Backtest: select 3–5 HS product categories with known historical reshoring narratives (2018–2024, post-tariff-war and post-COVID supply-chain-diversification periods); construct sector-ETF or basket-level portfolio conditioned on the origin-share-shift signal; test against sector-relative (not market-relative) returns to isolate the effect from broad market moves, using a difference-in-differences design comparing high-exposure versus low-exposure firms within the same sector.
Pitfall: UN Comtrade data itself has a multi-month reporting lag (partially offsetting the "leading indicator" claim — must be validated empirically, not assumed); firm-level attribution requires a supply-chain-exposure mapping that doesn't exist in any clean public dataset (must be hand-built from 10-K supply-chain disclosures or paid databases).

**11. ENSO-forecast-versus-weather-derivative-implied mispricing in agricultural/energy commodities.**
Theory: NOAA/NWS El Niño-Southern Oscillation probabilistic forecasts are public, free, and updated monthly; if weather-derivative or commodity-options-implied pricing doesn't fully and immediately incorporate the latest ENSO forecast update, a systematic mispricing window may exist around each monthly forecast release.
Data: NOAA Climate Prediction Center ENSO forecast API/bulletins (free, official), CME agricultural/natural-gas futures and options data.
Signal: change in ENSO forecast probability (e.g., La Niña probability shift) at each monthly CPC update, mapped to historically ENSO-sensitive commodities (grain futures for El Niño/La Niña-driven yield effects, natural gas for winter-demand effects).
Backtest: event-study around each monthly CPC ENSO bulletin release date, 2000–2025 (long sample available, genuine statistical power); measure abnormal returns/implied-vol changes in ENSO-sensitive futures in the 1–5 trading days following each bulletin, conditioned on the magnitude of forecast-probability revision; benchmark against a random-day placebo sample to establish the bulletin-day effect is genuinely event-driven, not just typical commodity-market noise.
Pitfall: commodity markets are already heavily populated by dedicated weather-trading desks at merchant trading houses (Cargill, ADM in-house desks, and specialized weather-derivative funds) who almost certainly already price ENSO updates efficiently — a rigorous prior here should be skeptical, and the backtest should be explicitly designed to detect whether *any* residual mispricing survives, not assumed to exist.

**12. PACER/CourtListener litigation-docket surge as securities-fraud/settlement pricing signal.**
Theory: securities-class-action filing surges (visible in real-time federal court dockets) and subsequent docket-activity intensity (motion-to-dismiss outcomes, settlement-conference scheduling) predict both near-term negative price pressure (filing) and, later, settlement-related information (docket activity intensifying ahead of a scheduled settlement announcement).
Data: CourtListener/RECAP API (free access to a large, growing archive of PACER federal court filings — a genuinely excellent free alternative to paid PACER access), Stanford Securities Class Action Clearinghouse (free, comprehensive historical securities-litigation database) for validation/labeling.
Signal: (a) new-filing flag as an event marker, (b) rolling docket-activity-intensity (filings-per-week in a given case) as a settlement-proximity proxy.
Backtest: universe of all securities class actions in the Stanford SCAC database, 2010–2024; event-study around filing date (expected, likely small incremental signal beyond the news itself, since filings are immediately publicized) versus the less-obvious docket-activity-intensity signal as a predictor of settlement-announcement timing (a duration/survival-analysis model — Cox proportional hazards — predicting time-to-settlement-announcement as a function of docket-activity features) with implied-vol-crush trading around predicted settlement windows as the tested strategy.
Pitfall: filing-date reaction is almost certainly already efficient (immediate news coverage); the genuinely novel part (docket-activity-based settlement-timing prediction) requires real legal-process domain knowledge to correctly interpret docket-entry types, and is a smaller, more specialized edge.

**13. Wikipedia edit-velocity and edit-war intensity as an attention proxy distinct from search volume.**
Theory: Wikipedia edits (especially contentious "edit wars," reflected in edit-frequency spikes and revert-frequency) around a company or executive's page reflect a different, arguably more informed/engaged attention population than passive Google searches, and the data is officially free and precisely timestamped (unlike Google Trends' unofficial, relative, revisable data).
Data: Wikipedia Pageviews API and the MediaWiki revision-history API (both official, free, fully timestamped to the second).
Signal: rolling edit-count and unique-editor-count z-scores per company/executive Wikipedia page, plus a "controversy" sub-score (revert-rate — edits reversed by other editors within 24 hours, indicating contested/disputed content, often correlating with breaking negative news before it's fully confirmed in mainstream media).
Backtest: S&P 1500 universe, 2015–2025 (long, clean, free sample — a genuine advantage of this dataset over Google Trends); regress forward 1/5/20-day abnormal returns on lagged edit-velocity and revert-rate z-scores, controlling for the standard Da-Engelberg-Gao search-volume signal (H13) to test whether Wikipedia activity carries genuinely *incremental* information beyond search volume, not just a correlated re-statement of the same underlying attention shock.
Pitfall: much lower baseline edit volume than search volume for smaller/less-famous companies (signal is sparse and noisy outside large-caps); edit-war/controversy content sometimes reflects already-public breaking news rather than leading it, requiring careful timestamp-precedence analysis versus news-wire timestamps to establish genuine lead time.

**14. Board-interlock network centrality as an information-hub lead-lag predictor.**
Theory: extending the Cohen-Frazzini (H1) economic-link framework from supply chains to **board-of-directors interlocks** — a director sitting on multiple public-company boards is a plausible private-information-diffusion conduit (board discussions of one company's strategy/outlook may inform that director's trading or advisory behavior at another company they sit on), and this network structure is less studied and less systematized by data vendors than supply-chain linkages.
Data: SEC DEF 14A proxy statements (director biographical/board-membership disclosures, free via EDGAR full-text search), Form 4 insider-trading data for the directors themselves (free, EDGAR).
Signal: for each pair of companies sharing a common director, compute a "hub-return" lead signal — does company A's abnormal return predict company B's abnormal return in the following 5–10 trading days, conditional on a shared-director link, more strongly than for a matched non-linked pair?
Backtest: build the board-interlock graph from DEF 14A filings for the Russell 3000, 2010–2024 (a genuinely substantial NLP/entity-resolution project — director name disambiguation across companies and over time is nontrivial); for each linked pair, run a Granger-causality/lead-lag regression of B's return on A's lagged returns, controlling for industry and size, benchmarked against a bootstrap-resampled placebo set of random (non-interlocked) company pairs matched on the same size/industry characteristics to isolate the interlock-specific effect.
Pitfall: entity resolution (matching the same real person across filings with name variants, e.g., "Robert J. Smith" vs. "Bob Smith") is a genuinely hard, error-prone data-engineering problem that materially affects signal quality if done sloppily; the number of *truly* independent director-linked pairs (not correlated through shared industry membership, which is a confound that must be explicitly controlled for) may be smaller than it first appears.

**15. Municipal-bond issuance-calendar and underwriter-syndicate composition as a regional-bank health index.**
Theory: municipal-bond issuance volume, timing, and the composition of underwriting syndicates (which regional/community banks participate as co-managers) in a given metro area serve as a real-time proxy for regional economic activity and, specifically, regional-bank underwriting-fee-income health — visible well before it's aggregated into regional Fed data or bank quarterly disclosures.
Data: EMMA (Electronic Municipal Market Access, MSRB's official free database — comprehensive, free, and underused in the retail-quant community) for muni issuance and underwriter data.
Signal: rolling issuance-volume and underwriter-syndicate-diversity index by MSA (metropolitan statistical area), mapped to publicly-traded regional banks headquartered/concentrated in that MSA.
Backtest: universe of regional bank holding companies (KRE constituents and similar), 2015–2024; regress next-quarter fee-income (non-interest-income) surprise on the lagged MSA-level muni-issuance-activity signal, controlling for interest-rate environment (muni issuance is itself rate-sensitive, a genuine confound requiring explicit control via a rate-environment interaction term); portfolio sort within the regional-bank universe on the signal.
Pitfall: attribution of an MSA-level signal to a specific bank's actual underwriting-desk revenue requires assuming a stable relationship between local muni activity and that specific bank's participation share, which may not hold if a bank's muni desk footprint changes (acquisition, desk shutdown) — this needs explicit tracking, not a static mapping.

**16. FEMA disaster declarations versus insurer cat-bond spread divergence (ILS relative value).**
Theory: catastrophe-bond spreads should reprice promptly and accurately in response to FEMA disaster declarations and NOAA storm-track updates during an active event; transient dislocations between the "modeled" loss-probability implied by cat-bond spreads and the actual, publicly-available disaster-declaration/storm-track data may create short-lived relative-value opportunities, particularly in less-liquid, single-peril cat bonds versus more-liquid diversified ones.
Data: FEMA OpenFEMA API (free, official disaster-declaration data), NOAA National Hurricane Center storm-track data (free, official), cat-bond pricing (Artemis.bm provides substantial free market commentary/data; full pricing history is a paid institutional product via Swiss Re/AM Best or specialized ILS data vendors).
Signal: divergence between a cat bond's spread-implied loss probability (back-solved from pricing and modeled-loss assumptions) and a simple, publicly-reconstructable loss-probability estimate derived from real-time storm-track/declaration data during an active event window.
Backtest: event-study design around named Atlantic hurricane seasons with active cat-bond exposure, 2010–2024 (a case-study/event-study design given the relatively small number of major landfalling-hurricane events with liquid cat-bond exposure in any given season — explicitly lower-N than a cross-sectional equity backtest); measure whether cat-bond spread reversion post-event correlates with the pre-event divergence signal.
Pitfall: cat-bond market is genuinely illiquid and dominated by specialized ILS funds with proprietary catastrophe models (RMS, AIR/Verisk) that are far more sophisticated than any publicly-reconstructable estimate — a realistic prior is that this is a very hard market to find retail-accessible edge in, and the idea's primary value may be as a risk-monitoring/relative-value screening tool rather than a standalone alpha source.

**17. FCC ULS/tower-permit filings as telecom-capex and tower-REIT leading indicator.**
Theory: cell-tower construction and spectrum-deployment activity requires FCC Universal Licensing System filings and local zoning permits, both public record, months before the resulting capex/lease-revenue shows up in telecom and tower-REIT (American Tower, Crown Castle, SBA Communications) quarterly disclosures.
Data: FCC ULS API/bulk data (free, official), local zoning-permit data (highly fragmented, county-by-county — a genuine data-engineering challenge, potentially limit initial scope to a sample of major MSAs rather than attempting full national coverage).
Signal: rolling new-filing count by carrier and by tower-REIT-operated site, aggregated regionally.
Backtest: tower-REIT universe (small N, so this is closer to a macro/thematic timing signal for the sector than a cross-sectional stock-picking signal) 2015–2024; regress next-2-quarter tower-REIT organic-growth/leasing-revenue guidance on the lagged FCC-filing-activity signal; given the small cross-section (3–4 major tower REITs), emphasize time-series predictive power (does filing-activity growth lead leasing-revenue growth at the sector level) over cross-sectional portfolio construction.
Pitfall: genuinely small universe of investable pure-play tower REITs limits statistical power and makes this more suited to a qualitative/quantamental overlay than a fully systematic strategy; permit-to-active-lease timelines are long and variable, diluting the "leading indicator" precision.

**18. Vocal-biomarker stress analysis of earnings-call executives.**
Theory: acoustic-forensic research (from the deception-detection and clinical-psychology literature, not finance) finds measurable vocal-stress correlates (pitch variance, pause-length changes, speech-rate changes relative to an individual's own baseline) associated with cognitive load/deception; applying this to earnings-call audio (rather than transcript text alone) for CEOs/CFOs during unscripted Q&A may capture stress signals invisible to text-only NLP (H2/H12).
Data: earnings-call webcast audio (many companies host public replay audio on IR websites — a genuinely underused free data source since most alt-data vendors focus on the transcript text, not the raw audio), open-source acoustic-feature-extraction tools (`openSMILE`, `Praat`/`parselmouth`).
Signal: per-executive, per-call acoustic-stress composite (pitch-variance z-score, pause-frequency z-score, speech-rate z-score, each computed relative to that specific executive's own historical baseline across prior calls — critically, cross-executive comparison is far noisier than within-executive-over-time comparison, since baseline vocal characteristics vary enormously by individual).
Backtest: build an executive-level panel requiring ≥8 historical calls per executive (to establish a stable individual baseline) across a sample of S&P 500 companies, 2015–2024; regress the acoustic-stress composite (isolated to the unscripted Q&A segment specifically, not prepared remarks) on subsequent 90-day guidance-revision direction and magnitude, controlling for the text-based tone signal (H12) to test incremental information content of the *audio* channel specifically, beyond what's already captured in the transcript text.
Pitfall: audio-quality and recording-setup heterogeneity across companies/years introduces substantial measurement noise that must be carefully normalized; a genuinely novel and under-researched area in finance specifically (though well-established methodologically in forensic psychology), meaning there is limited existing financial-domain validation to benchmark expected effect sizes against — treat initial results with extra skepticism and budget for a dedicated pilot study on a small, high-quality-audio subsample before scaling.

**19. Open-source GitHub commit/contributor-churn velocity for public software companies.**
Theory: for public companies with significant open-source-maintained components (common in developer-tools, infrastructure, and increasingly AI companies), GitHub commit velocity, contributor-churn, and issue-resolution-time trends are a free, real-time, granular proxy for product-development momentum and engineering-team health, visible well before product-launch or revenue effects show up in quarterly disclosures.
Data: GitHub REST/GraphQL API (free, generous rate limits for research use), mapping of public companies to their maintained open-source repositories (must be hand-curated — no clean existing public mapping).
Signal: rolling commit-frequency, unique-contributor-count, and core-maintainer-retention (a proxy for internal team stability — sudden departure of long-tenured core maintainers is a potentially meaningful signal analogous to executive-departure signals in idea #27) trends per company's key repositories.
Backtest: universe of public developer-tools/infrastructure companies with a maintained flagship open-source repo (e.g., a sample of 30–50 identifiable companies, 2018–2025 — small-N, sector-specific); regress next-2-quarter revenue-growth surprise on lagged commit-velocity/contributor-churn signals, controlling for overall sector momentum; given small N, supplement the cross-sectional regression with individual company case-study validation.
Pitfall: mapping companies to repos and correctly attributing commit activity to "core product health" versus noise (many commits are trivial/automated, e.g., dependency-bot updates) requires careful filtering; the universe of applicable companies is inherently small and sector-concentrated, limiting generalizability and statistical power.

**20. District-level Beige Book text NLP for regional-bank/REIT relative performance.**
Theory: the Federal Reserve's Beige Book is compiled from 12 regional Fed districts and released with district-specific qualitative commentary before being synthesized into the national summary that markets primarily react to; district-level tone/topic shifts may contain regionally-specific information not fully reflected in regional-bank or regional-REIT pricing until the (lagged, aggregated) national data catches up.
Data: Federal Reserve Beige Book full text archive (free, official, going back decades, released 8 times/year on a known schedule).
Signal: per-district NLP sentiment/topic-shift score (using the Loughran-McDonald financial dictionary or an LLM classifier) computed separately for each of the 12 district reports, compared to that district's own trailing-4-release baseline.
Backtest: map regional banks/REITs to their primary Fed district by headquarters/asset-concentration location; construct a district-relative long/short portfolio (long banks/REITs in districts with improving Beige Book sentiment, short those in deteriorating districts), rebalanced at each of the 8 annual release dates, 2005–2024 (a long, clean, entirely free sample — one of the more statistically well-powered ideas in this list given the multi-decade release history); benchmark against the national Beige Book sentiment signal alone to isolate whether district-level granularity adds incremental value over the market-wide reaction.
Pitfall: Beige Book release reactions may already be reasonably efficient at the national level (it's a widely-followed release), so the entire thesis rests on the district-granularity angle specifically being under-exploited — this should be tested as the primary hypothesis, not assumed.

**21. County-level unemployment-claims/OSHA-establishment cross-reference for pre-WARN-Act layoff nowcasting.**
Theory: the federal WARN Act requires 60-day advance notice of mass layoffs (state WARN databases are public record but fragmented/inconsistently digitized), and county-level unemployment-insurance-claims micro-data, cross-referenced with a company's disclosed facility locations (10-K Item 2 "Properties," OSHA establishment-location data), can potentially nowcast layoff activity even before formal WARN notices are filed or aggregated nationally.
Data: state-level WARN Act notice databases (free but genuinely fragmented — 50 different state systems, a real data-engineering undertaking), Bureau of Labor Statistics county-level unemployment-claims data via the BLS API (free, official), 10-K Item 2 property disclosures (EDGAR, requires NLP extraction of facility addresses).
Signal: county-level unemployment-claims anomaly (relative to that county's own seasonal baseline) cross-referenced against counties where a specific public company has a disclosed major facility, weighted by that facility's estimated headcount share of the company's total workforce (a genuinely difficult sub-signal to estimate precisely, likely requiring approximation from facility square-footage or industry-typical headcount density).
Backtest: universe of companies with large, geographically-concentrated single facilities (manufacturing, logistics — easier to attribute a county-level signal to a specific company than for geographically-diffuse service companies), 2015–2024; regress next-quarter guidance-cut probability on the lagged county-claims-anomaly signal, controlling for local-economy-wide effects (a county-level claims spike could reflect a *different* large local employer, not the target company — this confound must be explicitly addressed, e.g., by favoring counties/company pairs with minimal other large-employer overlap).
Pitfall: attribution confound (as noted above) is the central methodological risk and must be a primary focus of the backtest design, not an afterthought; WARN database fragmentation across states means initial scope should realistically be limited to a subset of well-digitized states rather than attempting full national coverage from day one.

**22. VIIRS nighttime-lights growth as an EM/frontier-market GDP-nowcast trading signal.**
Theory: NASA/NOAA VIIRS nighttime-lights satellite data is a well-established academic proxy for sub-national economic activity (extensively used in development economics), genuinely free at reasonable resolution, and can nowcast GDP growth in emerging/frontier markets faster than official (often delayed, sometimes unreliable) government GDP statistics, creating a tradeable edge in country-level EM/frontier ETFs or currency positions around GDP-surprise-sensitive events.
Data: NOAA/NASA VIIRS Day/Night Band nighttime-lights data (genuinely free, monthly composite tiles available), official GDP-release-calendar data by country, EM/frontier country ETF prices.
Signal: rolling country-level aggregate nighttime-light-radiance growth rate, computed via straightforward raster-summation/change-detection using open-source tools (Google Earth Engine offers free-tier access sufficient for this analysis, `rasterio`/`xarray` for local processing).
Backtest: sample of 15–20 frontier/EM countries with investable single-country ETFs (e.g., EGPT, THD, VNM and similar) and historically volatile/surprise-prone GDP releases, 2015–2024; construct a GDP-surprise-prediction model using the nighttime-lights growth signal, tested against actual subsequent official GDP-release surprises (does the satellite-implied growth rate predict the sign/magnitude of the eventual official-data surprise relative to consensus); trade the relevant country ETF or local-currency position ahead of the official release based on the satellite-implied nowcast, with returns measured around the actual release-date reaction.
Pitfall: nighttime lights are a noisy proxy for genuinely diversified/service-heavy economies (works better for manufacturing/industrial-activity-heavy economies than service-dominated ones); cloud-cover and seasonal-lighting-pattern (e.g., holiday lighting) noise requires careful compositing/filtering methodology, an area with substantial existing academic literature (development-economics VIIRS papers) worth directly reviewing before building your own pipeline from scratch.

**23. FINRA ADF/dark-pool print imbalance versus signed options-clearing data for short-term reversal.**
Theory: distinct from GEX (H5), a short-term (intraday-to-multiday) reversal signal may exist by combining FINRA's alternative-trading-system (dark pool) volume data with large-options-trader-reporting data to infer a more direct measure of informed-versus-liquidity-driven order-flow imbalance than either data source provides alone.
Data: FINRA ADF/ORF aggregate dark-pool volume data (free, published with a short lag), OCC large options position reports (free, aggregate level; individual large-trader data requires a regulatory relationship, not publicly available at that granularity — a genuine data-access ceiling for this idea at the individual-researcher level).
Signal: divergence between dark-pool net volume imbalance (a liquidity-driven-flow proxy, since dark pools are disproportionately used for large, non-information-driven block trades) and lit-market options-implied directional positioning (from OI changes) — periods where the two signals strongly disagree may indicate one venue is being used for genuine information-driven positioning while the other reflects incidental liquidity flow.
Backtest: large-cap, heavily-dark-pool-traded universe (S&P 500), 2018–2024; construct the divergence signal and test forward 1–5 day return predictability, benchmarked directly against the GEX-only signal (H5) and dark-pool-imbalance-only signal individually, to isolate whether the *combination* adds incremental predictive power over either single-source signal.
Pitfall: individual-level signed options-trader data (the more powerful version of this signal) is not genuinely available to a public/individual researcher, meaning the achievable version of this idea is a materially weaker approximation of the full institutional-grade signal — set expectations accordingly, and treat this as a lower-conviction inclusion relative to most others in this list.

**24. Aviation-insurance renewal-pricing as a distress signal for airlines/private-aviation-heavy executives.**
Theory: aviation-insurance underwriters (a specialized, information-intensive insurance niche) price renewal premiums based on detailed risk assessments (fleet age/maintenance records, safety-incident history, financial-health-linked counterparty risk); premium-pricing trends, if obtainable even indirectly (e.g., via insurer earnings-call commentary on aviation-line loss ratios, or trade-press coverage of specific renewal cycles), could serve as a genuinely novel, under-exploited distress signal for airlines specifically.
Data: this is the most data-access-constrained idea in the list — no clean public API exists; feasible individual-researcher approach is limited to (a) insurer 10-K/earnings-call disclosures of aviation-line loss-ratio trends (aggregate, not company-specific — a real limitation), and (b) specialized trade press (e.g., Aviation Week, insurance trade publications) for qualitative renewal-cycle commentary, requiring manual/NLP monitoring rather than a clean structured feed.
Signal: aggregate aviation-insurance loss-ratio trend (from insurer disclosures) as a sector-wide (not company-specific) distress leading indicator for the airline sector.
Backtest: given the aggregate-only nature of the achievable data, this is realistically a sector-timing overlay (airline-sector-ETF, e.g., JETS, positioning) rather than a stock-selection signal; test whether insurer-disclosed aviation loss-ratio deterioration in a given period predicts subsequent airline-sector relative underperformance over the following 1–2 quarters, 2010–2024 (a modest-N case-study-style test given the low frequency of clean loss-ratio disclosures).
Pitfall: this idea is included as a genuinely speculative, low-data-availability inclusion specifically because the underlying economic logic is sound and unusual — an honest assessment is that it's the weakest idea in this list from a practical-implementability standpoint, appropriate for a research backlog item rather than a near-term build.

**25. arXiv/SSRN preprint velocity as a thematic-technology re-rating leading indicator.**
Theory: academic research-preprint velocity in a specific technical domain (e.g., a surge in battery-chemistry or quantum-error-correction preprints) often precedes, by 1–3 years, the domain's transition from "research" to "commercializable," which precedes thematic-ETF flows and forward re-rating of exposed public companies — testing whether the academic literature genuinely leads the market's thematic attention, or merely coincides with/lags it.
Data: arXiv API (free, official, full-text and metadata), SSRN (less API-friendly, may require scraping), thematic-ETF flow data (ETF.com, free basic flow data; more granular flow data is paid).
Signal: rolling preprint-count growth rate within a defined technical category (arXiv's own category taxonomy, e.g., cond-mat for battery materials, quant-ph for quantum computing) as a leading indicator for a mapped thematic-ETF's subsequent flow/price trend.
Backtest: select 4–6 identifiable technology themes with both (a) a clean arXiv category mapping and (b) an investable thematic ETF with several years of history (e.g., quantum computing, solid-state batteries, mRNA/gene-editing therapeutics), 2015–2024; Granger-causality test between category-level preprint-count growth and subsequent thematic-ETF price/flow trends, explicitly testing lead/lag direction (a real risk is that preprint velocity *follows* commercial/market attention, i.e., funding chases hype which then produces more papers, rather than leading it — the direction of causality is the actual research question here, not assumed).
Pitfall: small number of clean, mappable technology-theme/ETF pairs limits statistical power (this is a case-study-heavy design, similar to ideas #9, #16, #25); genuine risk that the causal direction runs opposite to the hypothesis (funding/hype → more papers, rather than papers → future hype), which must be tested rigorously (Granger causality in both directions) rather than assumed.

**26. Cross-listed ADR intraday price-discrepancy arbitrage conditioned on information-flow time-zone lag.**
Theory: extending the classic Eun-Sabherwal cross-listing-arbitrage literature with modern HFT-frequency data: time-zone gaps between a stock's home-market listing and its US ADR/cross-listing create windows where news breaking in one time zone hasn't yet been fully incorporated into the other market's price, and modern tick-level data allows testing whether this lag has genuinely closed (likely, given HFT/algorithmic cross-market arbitrage maturity) or whether residual, harder-to-arbitrage lag remains in specific less-liquid cross-listed pairs.
Data: tick-level trade data for a sample of cross-listed pairs (home-market exchange + US ADR), via Databento or Polygon.io (paid tick-data tiers), FX rates for currency-adjustment (ADR pricing must be currency-adjusted to compare against home-market pricing on a common basis).
Signal: intraday price-gap (currency-adjusted) between the ADR and its home-market-implied fair value during the home-market's active trading hours (when the ADR itself is not trading, i.e., testing whether the ADR's *next-open* price efficiently incorporates the full home-market move that occurred while the ADR was closed).
Backtest: sample of 20–30 liquid ADRs with active home-market cross-listings across different time-zone gaps (Asian ADRs with the largest time-zone gap from US hours are the most theoretically interesting case), 2018–2024, tick-level data; regress ADR opening-price gap versus home-market overnight move, testing whether the relationship is 1:1 (fully efficient) or shows systematic under/over-reaction, and specifically testing whether any residual inefficiency is large enough to survive realistic transaction costs and overnight funding/borrow costs for the arbitrage trade.
Pitfall: this is very likely a fully-arbitraged-away market at the large/liquid-ADR level given decades of institutional cross-listing-arbitrage activity (this is explicitly flagged as a high-prior-of-null-result idea) — genuine value is in rigorously establishing *whether* any residual edge exists in less-liquid cross-listed pairs specifically, which is itself a useful negative/positive result either way.

**27. Board-departure clustering combined with D&O insurance premium changes as governance-distress signal.**
Theory: individual director departures (Form 8-K Item 5.02) are common and mostly uninformative, but *clustering* of multiple unrelated-reason departures within a short window, combined with an increase in D&O (directors & officers) insurance premium (a market-priced signal of perceived governance/litigation risk, though genuinely hard to observe directly at the company level from public data), may jointly indicate governance distress not yet reflected in the stock price.
Data: SEC 8-K Item 5.02 filings (free, EDGAR, structured enough to extract departure events systematically), D&O insurance premium data (genuinely difficult — no clean public per-company source; the closest achievable proxy is insurer-level aggregate D&O pricing-trend commentary from insurer earnings calls/10-Ks, similar limitation to idea #24).
Signal: rolling 6-month count of "unrelated reason" director/officer departures (explicitly excluding routine end-of-term/retirement language, which requires NLP classification of the stated departure reason) as the primary, achievable signal; D&O-premium component realistically included only as a qualitative overlay given data-access limitations, not a clean quantitative input.
Backtest: universe of Russell 3000 companies, 2010–2024; construct the departure-clustering signal from 8-K NLP classification; regress forward 6-month abnormal returns and subsequent-restatement/litigation incidence on the clustering signal, controlling for company size and prior governance-quality proxies (e.g., ISS governance scores if accessible, or simpler proxies like board-independence ratio from proxy statements); this is achievable as a genuinely clean, free-data, decently-powered cross-sectional backtest even without the D&O-premium component.
Pitfall: "unrelated reason" classification from 8-K boilerplate language is genuinely difficult (companies routinely use vague, legally-vetted departure language regardless of true reason) and will introduce meaningful classification noise; the D&O-premium overlay, while theoretically the most interesting part of the hypothesis, is realistically not achievable as a clean quantitative signal from public data alone.

**28. Corporate sublease-listing/CoStar-adjacent office-give-back data as white-collar-layoff leading indicator.**
Theory: companies reducing headcount often give back excess office space via sublease listings before formal layoff announcements (subleasing has a lead time — legal/broker process — that plausibly precedes or coincides with, rather than follows, the workforce reduction itself), and commercial-real-estate sublease-listing data is a comparatively under-exploited-in-equity-research proxy for this.
Data: full CoStar data is paid and expensive (institutional CRE-data standard); lower-cost/free proxies include public commercial-real-estate listing aggregators (LoopNet has a public-facing listing search, scrapeable at a small/research scale with real ToS caveats) and local commercial-real-estate trade press.
Signal: rolling count/square-footage of new sublease listings associated with a specific company's known office addresses (requires mapping company facility addresses from 10-K Item 2 disclosures, similar entity-resolution challenge to idea #21).
Backtest: universe of large office-space-heavy employers (professional/financial/tech services companies with substantial disclosed office footprints), 2019–2024 (a period spanning the post-COVID office-space-reduction wave, giving genuine variation to test against); regress next-2-quarter headcount-reduction/restructuring-charge disclosure on the lagged sublease-listing-activity signal, controlling for company size and sector (tech/financial-services office-reduction trends had substantial sector-wide co-movement post-2022 that must be controlled for to isolate company-specific signal).
Pitfall: address-to-company mapping and sublease-listing-to-company attribution both require nontrivial entity resolution; the post-COVID period used for backtesting had unusually large sector-wide (not company-specific) office-reduction trends, which could dominate and dilute the company-specific signal unless carefully controlled for via sector-relative, not absolute, signal construction.

**29. Livestream concurrent-viewership/SteamDB player-count data as high-frequency gaming-revenue nowcast.**
Theory: for public gaming companies, Twitch/YouTube concurrent-viewership and SteamDB (or platform-equivalent) concurrent-player-count data provide a genuinely real-time (hourly/daily), free, granular proxy for game engagement/monetization trends, materially faster and more granular than the monthly app-download-based alt-data (H11-adjacent) that institutions already commonly use — the specific novelty claim here is that *player-count* (engagement/retention) is a meaningfully different, and for live-service/monetization-heavy titles arguably more revenue-relevant, signal than *download-count* (acquisition), which is the more commonly-used alt-data metric.
Data: SteamDB (unofficial but widely-used, scrapeable, free), Twitch API (official, free, generous rate limits) for concurrent-viewer counts as a secondary engagement proxy for titles with strong streaming-audience overlap.
Signal: rolling concurrent-player-count trend (daily peak and average) per title, aggregated to the parent public company level for companies with a dominant flagship live-service title (a real scoping constraint — works best for companies with one or two dominant titles, not highly diversified portfolios).
Backtest: universe of public gaming companies with a Steam-distributed flagship live-service title (a modest N, sector-specific), 2018–2025; regress next-quarter bookings/revenue surprise on lagged player-count-trend signal, explicitly benchmarked against app-download-based alt-data signals (where available, e.g., via SimilarWeb free tier) to test the specific claim that engagement/retention data (player-count) adds incremental predictive power beyond acquisition data (downloads) — this head-to-head comparison is the core, genuinely testable novel claim, not just "gaming alt-data predicts gaming revenue" in isolation.
Pitfall: works only for companies with a dominant, Steam/console-concurrent-player-trackable flagship title (excludes mobile-only or highly diversified gaming companies); monetization intensity varies enormously by title/business-model (free-to-play with microtransactions vs. premium one-time-purchase), meaning player-count-to-revenue conversion is not remotely uniform and must be modeled per-title/per-monetization-type, not pooled naively.

**30. Cross-manager hedge-fund-letter narrative-similarity as a systemic factor-crowding early-warning signal.**
Theory: extends the well-established "quant crowding" literature (which typically measures crowding via portfolio-holdings overlap, e.g., 13F-based position-overlap metrics) into the *unstructured-text* domain: if multiple hedge-fund quarterly investor letters independently converge on highly similar thematic narratives/stock theses (measurable via text-embedding cosine similarity across letters from different, unaffiliated managers) within the same period, this may be a genuinely earlier and more nuanced crowding signal than portfolio-overlap metrics alone, since narrative convergence can precede actual position-overlap (managers may be independently arriving at, and about to act on, the same thesis before their 13F filings reveal it).
Data: hedge-fund investor letters (no clean structured API — these are voluntarily, inconsistently published/leaked documents; aggregators like HedgeFundLetters.com or a self-built collection from public/leaked sources represent the realistic, imperfect data-access path; flag this explicitly as the weakest data-access link in an otherwise strong idea), embedding models (open-weight sentence-embedding models, e.g., a general-purpose or finance-domain-tuned sentence-transformer) for narrative-similarity scoring.
Signal: rolling quarterly cross-manager cosine-similarity score of investor-letter thematic content (embedding-based, focused specifically on stock/theme-mention passages rather than generic macro commentary) for a specific stock or theme; a signal spike (multiple independent managers converging narratively) flags elevated future-crowding/reversal risk for that name/theme.
Backtest: given the genuinely difficult and inconsistent data access, this is realistically a small-sample, hand-curated case-study backtest rather than a large systematic one; select 10–15 historical instances of documented "crowded trade" reversals (e.g., specific well-known hedge-fund-consensus-long names that subsequently experienced sharp reversals) and retrospectively test whether investor-letter narrative-similarity was detectably elevated in the 1–2 quarters *before* the reversal, compared to a matched control sample of non-reversal periods for similar stocks; given the small-N, case-study nature, results should be interpreted as hypothesis-generating rather than as a statistically powered standalone strategy, with the explicit goal of establishing whether the idea merits the substantial data-collection investment needed to test it properly at scale.
Pitfall: data access is genuinely the binding constraint on this idea (investor letters are not systematically, comprehensively, and legally cleanly available at scale) — of all 30 ideas, this one is most likely to be infeasible to test rigorously without either an existing personal network/subscription access to a large letter archive or a multi-year effort to build one, and should be prioritized accordingly (interesting hypothesis, weak near-term feasibility).

---

## Sources

- [PEAD.txt (JFQA)](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/peadtxt-postearningsannouncement-drift-using-text/5EB217BB68B5FB054FE38541BAAC4679)
- [Rest in Peace Post-Earnings Announcement Drift (Martineau, IDEAS/RePEc)](https://ideas.repec.org/p/osf/socarx/z7k3p.html)
- [Is Post-Earnings-Announcement Drift a Thing Again? (UCLA Anderson)](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/)
- [Economic Links and Predictable Returns (Cohen & Frazzini, AQR)](https://www.aqr.com/Insights/Research/Journal-Article/Economic-Links-and-Predictable-Returns)
- [Economic Links and Predictable Returns (original paper, Yale)](http://www.econ.yale.edu/~shiller/behfin/2006-04/cohen-frazzini.pdf)
- [Customer Momentum (arXiv replication)](https://arxiv.org/pdf/2301.11394)
- [The Disappearing Index Effect (Greenwood & Sammon, NBER WP 30748)](https://www.nber.org/system/files/working_papers/w30748/w30748.pdf)
- [The Disappearing Index Effect (HBS WP 23-025)](https://www.hbs.edu/ris/Publication%20Files/23-025_563e45c6-df92-4d9c-ae05-608d4d0acab1.pdf)
- [Is There an S&P 500 Index Effect? (NY Fed)](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr484.pdf)
- [From PIN to VPIN: An Introduction to Order Flow Toxicity (López de Prado)](https://www.quantresearch.org/From%20PIN%20to%20VPIN.pdf)
- [VPIN and the Flash Crash (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S1386418113000189)
- [Alternative Data for Hedge Funds Guide (Vertdata)](https://vertdata.com/blog/alternative-data-hedge-funds-guide)
- [5 Best Alternative Data Sources for Hedge Funds (ExtractAlpha)](https://extractalpha.com/2025/07/07/5-best-alternative-data-sources-for-hedge-funds/)
- [Gamma Exposure and S&P500 Return Predictability (Harbourfront Quant)](https://harbourfrontquant.substack.com/p/gamma-exposure-and-s-and-p500-return)
- [Gamma Exposure (GEX), SpotGamma](https://spotgamma.com/gamma-exposure-gex/)
- [...and the Cross-Section of Expected Returns (Harvey, Liu & Zhu, SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2249314)
- [...and the Cross-Section of Expected Returns (NBER WP 20592)](https://www.nber.org/system/files/working_papers/w20592/w20592.pdf)
- [The Growth and Limits of Arbitrage: Evidence from Short Interest (HBS)](https://www.hbs.edu/ris/Publication%20Files/The%20Growth%20and%20Limits%20of%20Arbitrage_199d963c-892f-4abc-b050-7a95ac089ba3.pdf)
- [Short Interest Effect (Quantpedia)](https://quantpedia.com/strategies/short-interest-effect-long-only-version)
- [In Search of Attention (Da, Engelberg & Gao, Journal of Finance)](https://www3.nd.edu/~zda/google.pdf)
- [Google Search Volume Index and Investor Attention: A Systematic Review (Financial Innovation)](https://link.springer.com/article/10.1186/s40854-023-00606-y)
- [Merger Arbitrage Opportunity (GMO)](https://www.gmo.com/americas/research-library/merger-arbitrage-opportunity_insights/)
- [Merger Spreads — Sources, Risks and Returns Examined (Alpha Architect)](https://alphaarchitect.com/2023/04/merger-spread/)
- [Carry Trades and Currency Crashes (Brunnermeier, Nagel & Pedersen, NBER WP 14473)](https://www.nber.org/system/files/working_papers/w14473/w14473.pdf)
- [How to Use 13F Filings (Trading Dude)](https://medium.com/@trading.dude/how-to-use-13f-filings-reading-the-hidden-hand-of-institutional-money-a5b7d07a514e)
- [Why Do Institutions Delay Reporting Their Shareholdings? Evidence from Form 13F (Wharton)](https://rodneywhitecenter.wharton.upenn.edu/wp-content/uploads/2014/04/13-15.musto_.pdf)
- [Alpha Decay (Di Mascio, Lines & Naik)](https://jhfinance.web.unc.edu/wp-content/uploads/sites/12369/2016/02/Alpha-Decay.pdf)
- [Earnings Conference Calls and Stock Returns: The Incremental Informativeness of Textual Tone (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0378426611002901)
- [Measuring Firm Complexity (Loughran & McDonald, JFQA)](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/measuring-firm-complexity/D737FD0A697AF699C5AADD62842ACAB8)
- [Cross-Sectional Variation of Option-Implied Volatility Skew (Management Science)](https://pubsonline.informs.org/doi/10.1287/mnsc.2023.4872)
- [Why Does Options Market Information Predict Stock Returns? (Journal of Financial Economics)](https://www.sciencedirect.com/science/article/pii/S0304405X25001618)
- [Playing the Field: Geomagnetic Storms and International Stock Markets (ResearchGate)](https://www.researchgate.net/publication/5026332_Playing_the_field_Geomagnetic_storms_and_international_stock_markets)
- [The Daylight Saving Time Anomaly in Stock Returns (Massey University)](https://www.massey.ac.nz/massey/fms/Massey%20News/2009/09/docs/DST_JFR_revised.pdf)
- [Are Investors Moonstruck? Lunar Phases and Stock Returns (RePEc)](https://ideas.repec.org:443/a/eee/empfin/v13y2006i1p1-23.html)
- [Empirical Asset Pricing via Machine Learning (Gu, Kelly & Xiu, Review of Financial Studies)](https://academic.oup.com/rfs/article/33/5/2223/5758276)
- [Empirical Asset Pricing via Machine Learning (Dacheng Xiu, full text)](https://dachxiu.chicagobooth.edu/download/ML.pdf)

*Note: several Part 4 ideas rely on data sources (job-board scrapes, employee-review platforms, hedge-fund letters) with meaningful Terms-of-Service and, in some cases, consumer-privacy-regulation constraints (especially credit-card panel data). Legal/compliance review is a prerequisite before any production deployment, not an afterthought — this is noted here once rather than repeated in every entry, but applies throughout Part 4.*
