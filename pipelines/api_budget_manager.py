"""
Manages the 500 calls/month IndianAPI budget.
Decides which stocks to fetch each day and which weekly endpoints to call.
"""

from __future__ import annotations
import logging
from datetime import date, datetime, timedelta
from data import supabase_client as db
from config.settings import INDIANAPI_MONTHLY_LIMIT, INDIANAPI_DAILY_STOCK_CALLS
from config.stock_universe import STOCK_UNIVERSE

logger = logging.getLogger(__name__)


def get_budget_status() -> dict:
    """Returns current month API usage stats."""
    used = db.get_api_calls_this_month()
    return {
        "used": used,
        "limit": INDIANAPI_MONTHLY_LIMIT,
        "remaining": INDIANAPI_MONTHLY_LIMIT - used,
        "pct_used": round(used / INDIANAPI_MONTHLY_LIMIT * 100, 1),
    }


def get_daily_allocation() -> int:
    """How many /stock calls we can make today."""
    status = get_budget_status()
    remaining = status["remaining"]

    # Estimate remaining trading days in month
    today = date.today()
    last_day = today.replace(day=28) + timedelta(days=4)
    last_day = last_day.replace(day=1) - timedelta(days=1)
    remaining_days = sum(
        1 for d in range(today.day, last_day.day + 1)
        if date(today.year, today.month, d).weekday() < 5
    )
    remaining_days = max(remaining_days, 1)

    # Reserve 5 calls/day for market-level endpoints + buffer
    available_for_stocks = remaining - (remaining_days * 5) - 10
    daily_stock_calls = min(
        INDIANAPI_DAILY_STOCK_CALLS,
        max(0, available_for_stocks // remaining_days)
    )
    return daily_stock_calls


def select_stocks_for_today(n: int | None = None) -> list[dict]:
    """
    Select which stocks to call /stock on today.
    Priority: staleness > volatility > nifty50 preference.
    Returns list of stock dicts from STOCK_UNIVERSE.
    """
    if n is None:
        n = get_daily_allocation()

    if n <= 0:
        return []

    # Get last fetch date for each stock from sentiment_scores
    all_sentiments = db.query(
        "sentiment_scores",
        select="stock_id,date",
        order="-date",
    )

    # Build stock_id -> last_fetch_date
    stock_ids = db.get_all_stock_ids()
    symbol_to_id = stock_ids
    id_to_symbol = {v: k for k, v in stock_ids.items()}

    last_fetched = {}
    for row in all_sentiments:
        sid = row["stock_id"]
        if sid not in last_fetched:
            last_fetched[sid] = row["date"]

    # Score each stock
    today = date.today()
    scored = []
    for stock in STOCK_UNIVERSE:
        symbol = stock["symbol"]
        sid = symbol_to_id.get(symbol)
        if sid is None:
            continue

        last_date = last_fetched.get(sid)
        if last_date:
            if isinstance(last_date, str):
                last_date = date.fromisoformat(last_date)
            staleness = (today - last_date).days
        else:
            staleness = 999  # never fetched = highest priority

        # Nifty 50 gets slight boost
        nifty_boost = 2 if stock["is_nifty50"] else 0

        score = staleness + nifty_boost
        scored.append((score, stock))

    # Sort by score descending (highest priority first)
    scored.sort(key=lambda x: x[0], reverse=True)

    selected = [s[1] for s in scored[:n]]
    logger.info(
        f"Selected {len(selected)} stocks for today: "
        f"{[s['symbol'] for s in selected]}"
    )
    return selected


def is_weekly_run_day() -> bool:
    """Weekly extra calls happen on Mondays."""
    return date.today().weekday() == 0


def get_stocks_for_weekly_targets(n: int = 10) -> list[dict]:
    """Select stocks for /stock_target_price weekly rotation."""
    # Similar staleness logic but using analyst_data table
    all_analyst = db.query("analyst_data", select="stock_id,date", order="-date")

    stock_ids = db.get_all_stock_ids()
    symbol_to_id = stock_ids

    last_fetched = {}
    for row in all_analyst:
        sid = row["stock_id"]
        if sid not in last_fetched:
            last_fetched[sid] = row["date"]

    today = date.today()
    scored = []
    for stock in STOCK_UNIVERSE:
        sid = symbol_to_id.get(stock["symbol"])
        if sid is None:
            continue
        last_date = last_fetched.get(sid)
        if last_date:
            if isinstance(last_date, str):
                last_date = date.fromisoformat(last_date)
            staleness = (today - last_date).days
        else:
            staleness = 999
        scored.append((staleness, stock))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [s[1] for s in scored[:n]]
