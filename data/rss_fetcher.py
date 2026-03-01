"""
RSS News Fetcher for Indian stock market news.
Fetches headlines from Google News RSS, Moneycontrol, Economic Times, etc.
Filters by stock name, industry, and general market keywords.
"""

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# RSS feeds for Indian financial news
RSS_FEEDS = {
    "google_finance_india": "https://news.google.com/rss/search?q={query}+stock+india&hl=en-IN&gl=IN&ceid=IN:en",
    "economic_times_markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "moneycontrol_news": "https://www.moneycontrol.com/rss/marketreports.xml",
    "livemint_markets": "https://www.livemint.com/rss/markets",
}

# General market / global feeds
MARKET_FEEDS = {
    "et_markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "google_global_markets": "https://news.google.com/rss/search?q=stock+market+india+nifty&hl=en-IN&gl=IN&ceid=IN:en",
    "google_global_economy": "https://news.google.com/rss/search?q=global+economy+markets&hl=en-IN&gl=IN&ceid=IN:en",
}

# Industry keywords for RSS search
INDUSTRY_KEYWORDS = {
    "IT": ["IT services", "software", "technology", "Infosys", "TCS", "Wipro"],
    "Financials": ["banking", "NBFC", "insurance", "financial services"],
    "Energy": ["oil gas", "energy", "petroleum", "refinery"],
    "FMCG": ["FMCG", "consumer goods", "fast moving"],
    "Automobile": ["automobile", "auto", "EV", "electric vehicle"],
    "Healthcare": ["pharma", "healthcare", "pharmaceutical"],
    "Materials": ["metals", "mining", "steel", "cement"],
    "Telecom": ["telecom", "5G", "broadband"],
    "Real Estate": ["real estate", "realty", "housing"],
    "Industrials": ["infrastructure", "defence", "industrial"],
    "Consumer Discretionary": ["retail", "consumer", "e-commerce"],
}


def _parse_rss(content: str) -> List[Dict]:
    """Parse RSS XML content into list of headline dicts."""
    items = []
    try:
        root = ET.fromstring(content)
        for item in root.iter("item"):
            title = item.findtext("title", "").strip()
            pub_date = item.findtext("pubDate", "")
            link = item.findtext("link", "")
            description = item.findtext("description", "").strip()

            if not title:
                continue

            # Parse publication date
            timestamp = None
            for fmt in [
                "%a, %d %b %Y %H:%M:%S %z",
                "%a, %d %b %Y %H:%M:%S GMT",
                "%Y-%m-%dT%H:%M:%S%z",
            ]:
                try:
                    timestamp = datetime.strptime(pub_date.strip(), fmt)
                    break
                except (ValueError, AttributeError):
                    continue

            if timestamp is None:
                timestamp = datetime.now()

            items.append({
                "title": title,
                "description": description[:300] if description else "",
                "timestamp": timestamp.isoformat(),
                "link": link,
            })
    except ET.ParseError as e:
        logger.debug(f"RSS parse error: {e}")
    return items


def _fetch_feed(url: str, timeout: int = 10) -> List[Dict]:
    """Fetch and parse a single RSS feed."""
    try:
        resp = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (compatible; MLStockBot/1.0)"
        })
        if resp.status_code == 200:
            return _parse_rss(resp.text)
    except Exception as e:
        logger.debug(f"Failed to fetch {url}: {e}")
    return []


def fetch_stock_news_for_date(stock_name: str, symbol: str,
                              target_date: str) -> List[Dict]:
    """
    Fetch news for a stock around a specific date using Google News date filters.
    target_date: 'YYYY-MM-DD' string.
    Uses after:/before: query params to get news from that day +/- 1 day.
    """
    from datetime import date as date_type
    d = datetime.strptime(target_date, "%Y-%m-%d").date()
    after = (d - timedelta(days=1)).isoformat()
    before = (d + timedelta(days=2)).isoformat()  # exclusive

    clean_symbol = symbol.replace(".NS", "").replace(".BO", "")
    queries = [stock_name, clean_symbol] if clean_symbol else [stock_name]

    all_items = []
    seen_titles = set()

    for q in queries:
        search = f"{q} stock after:{after} before:{before}"
        url = RSS_FEEDS["google_finance_india"].format(query=quote(search))
        items = _fetch_feed(url)
        for item in items:
            title_key = item["title"].lower()[:60]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                all_items.append(item)

    return all_items


def fetch_stock_news(stock_name: str, symbol: str = "",
                     max_age_days: int = 2) -> List[Dict]:
    """
    Fetch recent news for a specific stock.
    Searches Google News RSS by stock name and symbol.
    """
    # Build search queries
    queries = [stock_name]
    if symbol:
        clean_symbol = symbol.replace(".NS", "").replace(".BO", "")
        queries.append(clean_symbol)

    all_items = []
    seen_titles = set()
    cutoff = datetime.now() - timedelta(days=max_age_days)

    for query in queries:
        url = RSS_FEEDS["google_finance_india"].format(query=quote(query))
        items = _fetch_feed(url)
        for item in items:
            title_key = item["title"].lower()[:60]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                # Filter by age
                try:
                    ts = datetime.fromisoformat(item["timestamp"])
                    if ts.replace(tzinfo=None) >= cutoff:
                        all_items.append(item)
                except (ValueError, TypeError):
                    all_items.append(item)

    return all_items


def fetch_industry_news(sector: str, max_age_days: int = 2) -> List[Dict]:
    """
    Fetch recent news for an industry/sector.
    Uses sector-specific keywords.
    """
    keywords = INDUSTRY_KEYWORDS.get(sector, [sector])
    all_items = []
    seen_titles = set()
    cutoff = datetime.now() - timedelta(days=max_age_days)

    # Use first 2 keywords to limit RSS calls
    for keyword in keywords[:2]:
        query = f"{keyword} india stock market"
        url = RSS_FEEDS["google_finance_india"].format(query=quote(query))
        items = _fetch_feed(url)
        for item in items:
            title_key = item["title"].lower()[:60]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                try:
                    ts = datetime.fromisoformat(item["timestamp"])
                    if ts.replace(tzinfo=None) >= cutoff:
                        all_items.append(item)
                except (ValueError, TypeError):
                    all_items.append(item)

    return all_items


def fetch_market_news(max_age_days: int = 2) -> List[Dict]:
    """
    Fetch general market and global economy news.
    """
    all_items = []
    seen_titles = set()
    cutoff = datetime.now() - timedelta(days=max_age_days)

    for feed_name, url in MARKET_FEEDS.items():
        items = _fetch_feed(url)
        for item in items:
            title_key = item["title"].lower()[:60]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                try:
                    ts = datetime.fromisoformat(item["timestamp"])
                    if ts.replace(tzinfo=None) >= cutoff:
                        all_items.append(item)
                except (ValueError, TypeError):
                    all_items.append(item)

    return all_items


def fetch_all_news_for_stock(stock_name: str, symbol: str, sector: str,
                              max_age_days: int = 2) -> Dict[str, List[Dict]]:
    """
    Fetch stock-specific, industry, and market news in one call.
    Returns dict with keys: 'stock', 'industry', 'market'.
    """
    return {
        "stock": fetch_stock_news(stock_name, symbol, max_age_days),
        "industry": fetch_industry_news(sector, max_age_days),
        "market": fetch_market_news(max_age_days=max_age_days),
    }
