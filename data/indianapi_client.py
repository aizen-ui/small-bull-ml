"""
Rate-limited wrapper for indianapi.in Stock Market API.
Every call is logged to api_call_log table for budget tracking.
"""

from __future__ import annotations
import logging
import requests
from config.settings import INDIANAPI_KEY, INDIANAPI_BASE_URL, INDIANAPI_MONTHLY_LIMIT
from data import supabase_client as db

logger = logging.getLogger(__name__)


class BudgetExhaustedError(Exception):
    pass


def _check_budget() -> int:
    """Returns remaining calls this month. Raises if budget exhausted."""
    used = db.get_api_calls_this_month()
    remaining = INDIANAPI_MONTHLY_LIMIT - used
    if remaining <= 10:  # keep 10 as emergency buffer
        raise BudgetExhaustedError(
            f"IndianAPI budget nearly exhausted: {used}/{INDIANAPI_MONTHLY_LIMIT} used"
        )
    return remaining


def _call(endpoint: str, params: dict | None = None) -> dict | list | None:
    """Make a GET request to indianapi.in, log the call, return JSON."""
    remaining = _check_budget()
    logger.info(f"IndianAPI call: {endpoint} (params={params}, remaining={remaining})")

    url = f"{INDIANAPI_BASE_URL}{endpoint}"
    headers = {"X-Api-Key": INDIANAPI_KEY}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        db.log_api_call(endpoint, params, resp.status_code)

        if resp.status_code == 200:
            return resp.json()
        else:
            logger.error(f"IndianAPI error {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        db.log_api_call(endpoint, params, 0)
        logger.error(f"IndianAPI request failed: {e}")
        return None


# ── Endpoints ─────────────────────────────────────────────────

def get_stock(name: str) -> dict | None:
    """
    Get company data by name.
    Returns: tickerId, companyName, industry, currentPrice, recentNews,
             stockTechnicalData, analystView, riskMeter, etc.
    """
    return _call("/stock", {"name": name})


def get_trending() -> dict | None:
    """Get trending stocks (top gainers & losers)."""
    return _call("/trending")


def get_price_shockers() -> list | None:
    """Get stocks with unusual price movements."""
    return _call("/price_shockers")


def get_nse_most_active() -> list | None:
    """Get NSE most active stocks."""
    return _call("/NSE_most_active")


def get_bse_most_active() -> list | None:
    """Get BSE most active stocks."""
    return _call("/BSE_most_active")


def get_52_week_high_low() -> dict | None:
    """Get 52-week high/low data. May return empty when market is closed."""
    return _call("/fetch_52_week_high_low_data")


def get_commodities() -> list | None:
    """Get commodity futures data."""
    return _call("/commodities")


def get_stock_target_price(stock_id: str) -> dict | None:
    """Get analyst recommendations and price targets."""
    return _call("/stock_target_price", {"stock_id": stock_id})


def get_stock_forecasts(stock_id: str, measure_code: str = "EPS",
                        period_type: str = "Annual", data_type: str = "Estimates",
                        age: str = "Current") -> dict | None:
    """Get stock forecasts (EPS, ROE, Sales, etc.)."""
    return _call("/stock_forecasts", {
        "stock_id": stock_id,
        "measure_code": measure_code,
        "period_type": period_type,
        "data_type": data_type,
        "age": age,
    })


def get_historical_data(stock_name: str, period: str = "5yr",
                        filter_type: str = "default") -> dict | None:
    """Get historical stock data."""
    return _call("/historical_data", {
        "stock_name": stock_name,
        "period": period,
        "filter": filter_type,
    })


def get_historical_stats(stock_name: str,
                         stats: str = "quarter_results") -> dict | None:
    """Get historical financial statistics."""
    return _call("/historical_stats", {
        "stock_name": stock_name,
        "stats": stats,
    })


def get_industry_search(query_str: str) -> list | None:
    """Search for industry data."""
    return _call("/industry_search", {"query": query_str})
