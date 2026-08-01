"""
build_ticker_map.py -- hand-built CUSIP -> ticker mapping for the top-20-by-
value holdings of Berkshire Hathaway and Renaissance Technologies (2013+
13F-HR filings). Built from analyst domain knowledge, not a programmatic
CUSIP database (no free one is reachable from this environment) -- treat
this as a research-grade mapping, spot-checked but not institutionally
verified. status='delisted' flags securities that were acquired/merged/
delisted during the sample window; those get dropped from the return
backtest rather than papering over a broken price series.
"""
import pandas as pd

CUSIP_TICKER = {
    # Berkshire Hathaway holdings
    "00287Y109": ("ABBV", "active"),
    "00507V109": ("ATVI", "delisted_2023"),   # acquired by Microsoft
    "02005N100": ("ALLY", "active"),
    "02079K305": ("GOOG", "active"),
    "02079K107": ("GOOGL", "active"),
    "023135106": ("AMZN", "active"),
    "02376R102": ("AAL", "active"),
    "025816109": ("AXP", "active"),
    "G0403H108": ("AON", "active"),
    "037833100": ("AAPL", "active"),
    "060505104": ("BAC", "active"),
    "064058100": ("BK", "active"),
    "110122108": ("BMY", "active"),
    "14040H105": ("COF", "active"),
    "16119P108": ("CHTR", "active"),
    "166764100": ("CVX", "active"),
    "H1467J104": ("CB", "active"),
    "172967424": ("C", "active"),
    "191216100": ("KO", "active"),
    "21036P108": ("STZ", "active"),
    "22160K105": ("COST", "active"),
    "23918K108": ("DVA", "active"),
    "244199105": ("DE", "active"),
    "247361702": ("DAL", "active"),
    "25754A201": ("DPZ", "active"),
    "37045V100": ("GM", "active"),
    "38141G104": ("GS", "active"),
    "40434L105": ("HPQ", "active"),
    "459200101": ("IBM", "active"),
    "46625H100": ("JPM", "active"),
    "500754106": ("KHC", "active"),
    "501044101": ("KR", "active"),
    "530909308": ("LLYVK", "active"),
    "531229789": ("FWONK", "active"),
    "531229607": ("LSXMK", "active"),
    "57636Q104": ("MA", "active"),
    "58933Y105": ("MRK", "active"),
    "615369105": ("MCO", "active"),
    "61166W101": ("MON", "delisted_2018"),   # acquired by Bayer
    "650111107": ("NYT", "active"),
    "G6683N103": ("NU", "active"),
    "674599105": ("OXY", "active"),
    "68389X105": ("ORCL", "active"),
    "92556H206": ("PARA", "active"),
    "718546104": ("PSX", "active"),
    "829933100": ("SIRI", "active"),
    "833445109": ("SNOW", "active"),
    "844741108": ("LUV", "active"),
    "874039100": ("TSM", "active"),
    "903293405": ("USG", "delisted_2019"),   # acquired by Knauf
    "910047109": ("UAL", "active"),
    "91324P102": ("UNH", "active"),
    "902973304": ("USB", "active"),
    "92343E102": ("VRSN", "active"),
    "92343V104": ("VZ", "active"),
    "92826C839": ("V", "active"),
    "931142103": ("WMT", "active"),
    "949746101": ("WFC", "active"),
    # Renaissance Technologies holdings (additional, beyond overlap above)
    "002824100": ("ABT", "active"),
    "003654100": ("ABMD", "delisted_2022"),  # acquired by J&J
    "00724F101": ("ADBE", "active"),
    "007903107": ("AMD", "active"),
    "009066101": ("ABNB", "active"),
    "015351109": ("ALXN", "delisted_2021"),  # acquired by AstraZeneca
    "016255101": ("ALGN", "active"),
    "G0177J108": ("AGN", "delisted_2020"),   # acquired by AbbVie
    "01973R101": ("ALSN", "active"),
    "031162100": ("AMGN", "active"),
    "03831W108": ("APP", "active"),
    "04010E109": ("AGX", "active"),
    "G06242104": ("TEAM", "active"),
    "049468101": ("TEAM", "active"),
    "056752108": ("BIDU", "active"),
    "084670702": ("BRK-B", "active"),
    "084670108": ("BRK-A", "active"),
    "09062X103": ("BIIB", "active"),
    "097023105": ("BA", "active"),
    "11135F101": ("AVGO", "active"),
    "143658300": ("CCL", "active"),
    "146869102": ("CVNA", "active"),
    "12503M108": ("CBOE", "active"),
    "169656105": ("CMG", "active"),
    "12572Q105": ("CME", "active"),
    "218352102": ("CORT", "active"),
    "22788C105": ("CRWD", "active"),
    "256163106": ("DOCU", "active"),
    "25809K105": ("DASH", "active"),
    "278642103": ("EBAY", "active"),
    "29786A106": ("ETSY", "active"),
    "30161Q104": ("EXEL", "active"),
    "30231G102": ("XOM", "active"),
    "315616102": ("FFIV", "active"),
    "345370860": ("F", "active"),
    "34959E109": ("FTNT", "active"),
    "351858105": ("FNV", "active"),
    "36828A101": ("GEV", "active"),
    "369604103": ("GE", "active"),
    "375558103": ("GILD", "active"),
    "37733W105": ("GSK", "active"),
    "427866108": ("HSY", "active"),
    "433000106": ("HIMS", "active"),
    "437076102": ("HD", "active"),
    "G46188101": ("HZNP", "delisted_2023"),  # acquired by Amgen
    "444859102": ("HUM", "active"),
    "45337C102": ("INCY", "active"),
    "458140100": ("INTC", "active"),
    "478160104": ("JNJ", "active"),
    "496902404": ("KGC", "active"),
    "580135101": ("MCD", "active"),
    "30303M102": ("META", "active"),
    "595112103": ("MU", "active"),
    "594918104": ("MSFT", "active"),
    "60770K107": ("MRNA", "active"),
    "60855R100": ("MOH", "active"),
    "M7S64H106": ("MNDY", "active"),
    "61174X109": ("MNST", "active"),
    "64110L106": ("NFLX", "active"),
    "64125C109": ("NBIX", "active"),
    "654106103": ("NKE", "active"),
    "66987V109": ("NVS", "active"),
    "670100205": ("NVO", "active"),
    "67066G104": ("NVDA", "active"),
    "69608A108": ("PLTR", "active"),
    "697435105": ("PANW", "active"),
    "71654V408": ("PBR", "active"),
    "717081103": ("PFE", "active"),
    "722304102": ("PDD", "active"),
    "742718109": ("PG", "active"),
    "75734B100": ("RDDT", "active"),
    "770700102": ("HOOD", "active"),
    "771049103": ("RBLX", "active"),
    "80004C200": ("SNDK", "active"),
    "L8681T102": ("SPOT", "active"),
    "85207U105": ("S", "delisted_2020"),     # Sprint, merged into T-Mobile
    "85208M102": ("SFM", "active"),
    "855244109": ("SBUX", "active"),
    "87612E106": ("TGT", "active"),
    "88160R101": ("TSLA", "active"),
    "90353T100": ("UBER", "active"),
    "91307C102": ("UTHR", "active"),
    "92532F100": ("VRTX", "active"),
    "92857W308": ("VOD", "active"),
    "94419L101": ("W", "active"),
    "98980L101": ("ZM", "active"),
}

df = pd.DataFrame(
    [{"cusip": k, "ticker": v[0], "status": v[1]} for k, v in CUSIP_TICKER.items()]
)
df.to_csv("cusip_ticker_map.csv", index=False)
print(f"wrote {len(df)} CUSIP->ticker mappings")
print(df["status"].value_counts())

# cross-check against the actual top-20 file to see what's unmapped
uniq = pd.read_csv("top20_unique_issuers.csv")
unmapped = uniq[~uniq["cusip"].isin(df["cusip"])]
print(f"\nunmapped CUSIPs from top20_unique_issuers.csv: {len(unmapped)}")
if len(unmapped):
    print(unmapped.to_string(index=False))
