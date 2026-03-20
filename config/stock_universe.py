"""
Stock universe: Nifty 50 + select midcap/smallcap stocks.
Each entry maps yfinance symbol ↔ indianapi name ↔ metadata.
"""

STOCK_UNIVERSE = [
    # ── Nifty 50 ──────────────────────────────────────────────
    {"symbol": "RELIANCE.NS", "indianapi_name": "Reliance Industries", "company_name": "Reliance Industries Ltd", "sector": "Energy", "industry": "Oil & Gas - Refining & Marketing", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "TCS.NS", "indianapi_name": "TCS", "company_name": "Tata Consultancy Services Ltd", "sector": "IT", "industry": "IT Services & Consulting", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "HDFCBANK.NS", "indianapi_name": "HDFC Bank", "company_name": "HDFC Bank Ltd", "sector": "Financials", "industry": "Private Banks", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "INFY.NS", "indianapi_name": "Infosys", "company_name": "Infosys Ltd", "sector": "IT", "industry": "IT Services & Consulting", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "ICICIBANK.NS", "indianapi_name": "ICICI Bank", "company_name": "ICICI Bank Ltd", "sector": "Financials", "industry": "Private Banks", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "HINDUNILVR.NS", "indianapi_name": "Hindustan Unilever", "company_name": "Hindustan Unilever Ltd", "sector": "FMCG", "industry": "FMCG", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "SBIN.NS", "indianapi_name": "State Bank of India", "company_name": "State Bank of India", "sector": "Financials", "industry": "Public Banks", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "BHARTIARTL.NS", "indianapi_name": "Bharti Airtel", "company_name": "Bharti Airtel Ltd", "sector": "Telecom", "industry": "Telecom Services", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "KOTAKBANK.NS", "indianapi_name": "Kotak Mahindra Bank", "company_name": "Kotak Mahindra Bank Ltd", "sector": "Financials", "industry": "Private Banks", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "ITC.NS", "indianapi_name": "ITC", "company_name": "ITC Ltd", "sector": "FMCG", "industry": "FMCG", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "LT.NS", "indianapi_name": "Larsen and Toubro", "company_name": "Larsen & Toubro Ltd", "sector": "Industrials", "industry": "Construction & Engineering", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "AXISBANK.NS", "indianapi_name": "Axis Bank", "company_name": "Axis Bank Ltd", "sector": "Financials", "industry": "Private Banks", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "BAJFINANCE.NS", "indianapi_name": "Bajaj Finance", "company_name": "Bajaj Finance Ltd", "sector": "Financials", "industry": "NBFCs", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "MARUTI.NS", "indianapi_name": "Maruti Suzuki", "company_name": "Maruti Suzuki India Ltd", "sector": "Automobile", "industry": "Passenger Cars", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "HCLTECH.NS", "indianapi_name": "HCL Technologies", "company_name": "HCL Technologies Ltd", "sector": "IT", "industry": "IT Services & Consulting", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "TITAN.NS", "indianapi_name": "Titan Company", "company_name": "Titan Company Ltd", "sector": "Consumer Discretionary", "industry": "Jewellery", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "SUNPHARMA.NS", "indianapi_name": "Sun Pharma", "company_name": "Sun Pharmaceutical Industries Ltd", "sector": "Healthcare", "industry": "Pharmaceuticals", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "ASIANPAINT.NS", "indianapi_name": "Asian Paints", "company_name": "Asian Paints Ltd", "sector": "Consumer Discretionary", "industry": "Paints", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "BAJAJFINSV.NS", "indianapi_name": "Bajaj Finserv", "company_name": "Bajaj Finserv Ltd", "sector": "Financials", "industry": "Holding Companies", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "WIPRO.NS", "indianapi_name": "Wipro", "company_name": "Wipro Ltd", "sector": "IT", "industry": "IT Services & Consulting", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "ULTRACEMCO.NS", "indianapi_name": "UltraTech Cement", "company_name": "UltraTech Cement Ltd", "sector": "Materials", "industry": "Cement", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "NESTLEIND.NS", "indianapi_name": "Nestle India", "company_name": "Nestle India Ltd", "sector": "FMCG", "industry": "FMCG", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "TATAMOTORS.NS", "indianapi_name": "Tata Motors", "company_name": "Tata Motors Ltd", "sector": "Automobile", "industry": "Commercial Vehicles", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "NTPC.NS", "indianapi_name": "NTPC", "company_name": "NTPC Ltd", "sector": "Energy", "industry": "Power Generation", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "TATASTEEL.NS", "indianapi_name": "Tata Steel", "company_name": "Tata Steel Ltd", "sector": "Materials", "industry": "Iron & Steel", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "POWERGRID.NS", "indianapi_name": "Power Grid Corporation", "company_name": "Power Grid Corporation of India Ltd", "sector": "Energy", "industry": "Power Transmission", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "TECHM.NS", "indianapi_name": "Tech Mahindra", "company_name": "Tech Mahindra Ltd", "sector": "IT", "industry": "IT Services & Consulting", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "M&M.NS", "indianapi_name": "Mahindra and Mahindra", "company_name": "Mahindra & Mahindra Ltd", "sector": "Automobile", "industry": "Utility Vehicles", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "INDUSINDBK.NS", "indianapi_name": "IndusInd Bank", "company_name": "IndusInd Bank Ltd", "sector": "Financials", "industry": "Private Banks", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "ADANIENT.NS", "indianapi_name": "Adani Enterprises", "company_name": "Adani Enterprises Ltd", "sector": "Industrials", "industry": "Diversified", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "ONGC.NS", "indianapi_name": "ONGC", "company_name": "Oil & Natural Gas Corporation Ltd", "sector": "Energy", "industry": "Oil Exploration", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "JSWSTEEL.NS", "indianapi_name": "JSW Steel", "company_name": "JSW Steel Ltd", "sector": "Materials", "industry": "Iron & Steel", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "COALINDIA.NS", "indianapi_name": "Coal India", "company_name": "Coal India Ltd", "sector": "Energy", "industry": "Mining", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "GRASIM.NS", "indianapi_name": "Grasim Industries", "company_name": "Grasim Industries Ltd", "sector": "Materials", "industry": "Cement", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "ADANIPORTS.NS", "indianapi_name": "Adani Ports", "company_name": "Adani Ports and Special Economic Zone Ltd", "sector": "Industrials", "industry": "Port & Port Services", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "CIPLA.NS", "indianapi_name": "Cipla", "company_name": "Cipla Ltd", "sector": "Healthcare", "industry": "Pharmaceuticals", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "DRREDDY.NS", "indianapi_name": "Dr Reddys Laboratories", "company_name": "Dr. Reddy's Laboratories Ltd", "sector": "Healthcare", "industry": "Pharmaceuticals", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "BPCL.NS", "indianapi_name": "BPCL", "company_name": "Bharat Petroleum Corporation Ltd", "sector": "Energy", "industry": "Oil & Gas - Refining & Marketing", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "EICHERMOT.NS", "indianapi_name": "Eicher Motors", "company_name": "Eicher Motors Ltd", "sector": "Automobile", "industry": "Two Wheelers", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "DIVISLAB.NS", "indianapi_name": "Divis Laboratories", "company_name": "Divi's Laboratories Ltd", "sector": "Healthcare", "industry": "Pharmaceuticals", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "BRITANNIA.NS", "indianapi_name": "Britannia Industries", "company_name": "Britannia Industries Ltd", "sector": "FMCG", "industry": "FMCG", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "APOLLOHOSP.NS", "indianapi_name": "Apollo Hospitals", "company_name": "Apollo Hospitals Enterprise Ltd", "sector": "Healthcare", "industry": "Hospitals & Diagnostics", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "HEROMOTOCO.NS", "indianapi_name": "Hero MotoCorp", "company_name": "Hero MotoCorp Ltd", "sector": "Automobile", "industry": "Two Wheelers", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "HINDALCO.NS", "indianapi_name": "Hindalco Industries", "company_name": "Hindalco Industries Ltd", "sector": "Materials", "industry": "Aluminium", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "SBILIFE.NS", "indianapi_name": "SBI Life Insurance", "company_name": "SBI Life Insurance Company Ltd", "sector": "Financials", "industry": "Life Insurance", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "BAJAJ-AUTO.NS", "indianapi_name": "Bajaj Auto", "company_name": "Bajaj Auto Ltd", "sector": "Automobile", "industry": "Two Wheelers", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "TATACONSUM.NS", "indianapi_name": "Tata Consumer Products", "company_name": "Tata Consumer Products Ltd", "sector": "FMCG", "industry": "Tea & Coffee", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "HDFCLIFE.NS", "indianapi_name": "HDFC Life Insurance", "company_name": "HDFC Life Insurance Company Ltd", "sector": "Financials", "industry": "Life Insurance", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "LTIM.NS", "indianapi_name": "LTIMindtree", "company_name": "LTIMindtree Ltd", "sector": "IT", "industry": "IT Services & Consulting", "market_cap_category": "largecap", "is_nifty50": True},
    {"symbol": "WIPRO.NS", "indianapi_name": "Wipro", "company_name": "Wipro Ltd", "sector": "IT", "industry": "IT Services & Consulting", "market_cap_category": "largecap", "is_nifty50": True},

    # ── Extra Midcap / High-Interest Stocks ───────────────────
    {"symbol": "ETERNAL.NS", "indianapi_name": "Zomato", "company_name": "Eternal Ltd (Zomato)", "sector": "Consumer Discretionary", "industry": "Internet & Catalogue Retail", "market_cap_category": "largecap", "is_nifty50": False},
    {"symbol": "PAYTM.NS", "indianapi_name": "Paytm", "company_name": "One 97 Communications Ltd", "sector": "Financials", "industry": "Fintech", "market_cap_category": "midcap", "is_nifty50": False},
    {"symbol": "DMART.NS", "indianapi_name": "Avenue Supermarts", "company_name": "Avenue Supermarts Ltd", "sector": "Consumer Discretionary", "industry": "Retail", "market_cap_category": "largecap", "is_nifty50": False},
    {"symbol": "PIDILITIND.NS", "indianapi_name": "Pidilite Industries", "company_name": "Pidilite Industries Ltd", "sector": "Materials", "industry": "Specialty Chemicals", "market_cap_category": "largecap", "is_nifty50": False},
    {"symbol": "HAVELLS.NS", "indianapi_name": "Havells India", "company_name": "Havells India Ltd", "sector": "Consumer Discretionary", "industry": "Electrical Equipment", "market_cap_category": "largecap", "is_nifty50": False},
    {"symbol": "VEDL.NS", "indianapi_name": "Vedanta", "company_name": "Vedanta Ltd", "sector": "Materials", "industry": "Mining & Metals", "market_cap_category": "midcap", "is_nifty50": False},
    {"symbol": "DLF.NS", "indianapi_name": "DLF", "company_name": "DLF Ltd", "sector": "Real Estate", "industry": "Real Estate", "market_cap_category": "largecap", "is_nifty50": False},
    {"symbol": "TRENT.NS", "indianapi_name": "Trent", "company_name": "Trent Ltd", "sector": "Consumer Discretionary", "industry": "Retail", "market_cap_category": "largecap", "is_nifty50": False},
    {"symbol": "IRCTC.NS", "indianapi_name": "IRCTC", "company_name": "Indian Railway Catering & Tourism Corporation Ltd", "sector": "Industrials", "industry": "Tourism & Hospitality", "market_cap_category": "midcap", "is_nifty50": False},
    {"symbol": "HAL.NS", "indianapi_name": "Hindustan Aeronautics", "company_name": "Hindustan Aeronautics Ltd", "sector": "Industrials", "industry": "Aerospace & Defence", "market_cap_category": "largecap", "is_nifty50": False},
    {"symbol": "BEL.NS", "indianapi_name": "Bharat Electronics", "company_name": "Bharat Electronics Ltd", "sector": "Industrials", "industry": "Aerospace & Defence", "market_cap_category": "largecap", "is_nifty50": False},
    {"symbol": "TATAPOWER.NS", "indianapi_name": "Tata Power", "company_name": "Tata Power Company Ltd", "sector": "Energy", "industry": "Power Generation", "market_cap_category": "midcap", "is_nifty50": False},
    {"symbol": "DIXON.NS", "indianapi_name": "Dixon Technologies", "company_name": "Dixon Technologies (India) Ltd", "sector": "IT", "industry": "Electronic Equipment", "market_cap_category": "midcap", "is_nifty50": False},
    {"symbol": "POLYCAB.NS", "indianapi_name": "Polycab India", "company_name": "Polycab India Ltd", "sector": "Industrials", "industry": "Cables", "market_cap_category": "midcap", "is_nifty50": False},
    {"symbol": "JIOFIN.NS", "indianapi_name": "Jio Financial Services", "company_name": "Jio Financial Services Ltd", "sector": "Financials", "industry": "NBFCs", "market_cap_category": "largecap", "is_nifty50": False},
]

# Deduplicate (WIPRO appears twice in Nifty 50 list)
_seen = set()
_unique = []
for s in STOCK_UNIVERSE:
    if s["symbol"] not in _seen:
        _seen.add(s["symbol"])
        _unique.append(s)
STOCK_UNIVERSE = _unique

# Helpers
def get_symbols() -> list[str]:
    """All yfinance symbols."""
    return [s["symbol"] for s in STOCK_UNIVERSE]

def get_nifty50_symbols() -> list[str]:
    return [s["symbol"] for s in STOCK_UNIVERSE if s["is_nifty50"]]

def get_indianapi_name(symbol: str) -> str | None:
    for s in STOCK_UNIVERSE:
        if s["symbol"] == symbol:
            return s["indianapi_name"]
    return None

def get_stock_by_symbol(symbol: str) -> dict | None:
    for s in STOCK_UNIVERSE:
        if s["symbol"] == symbol:
            return s
    return None

def get_unique_sectors() -> list[str]:
    return list({s["sector"] for s in STOCK_UNIVERSE})
