"""Fetch stock data from yfinance (free, no API key needed)."""

from __future__ import annotations
import logging
from datetime import date
import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)


def fetch_daily(symbols: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
    """
    Fetch daily OHLCV for multiple symbols.
    Returns {symbol: DataFrame} with columns: date, open, high, low, close, volume
    """
    logger.info(f"Fetching daily data for {len(symbols)} symbols, period={period}")
    tickers_str = " ".join(symbols)
    raw = yf.download(tickers_str, period=period, auto_adjust=True,
                      group_by="ticker", threads=True)

    result = {}
    for symbol in symbols:
        try:
            # Extract per-symbol data from MultiIndex columns
            if isinstance(raw.columns, pd.MultiIndex):
                if symbol in raw.columns.get_level_values(-1):
                    df = raw.xs(symbol, level="Ticker", axis=1).copy()
                elif len(symbols) == 1:
                    df = raw.droplevel("Ticker", axis=1).copy()
                else:
                    logger.warning(f"No data for {symbol}")
                    continue
            else:
                df = raw.copy()

            df = df.dropna(subset=["Close"])
            if df.empty:
                logger.warning(f"No data for {symbol}")
                continue

            df = df.reset_index()
            df = df.rename(columns={
                "Date": "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            })
            # Keep only needed columns
            df = df[["date", "open", "high", "low", "close", "volume"]]
            df["date"] = pd.to_datetime(df["date"]).dt.date
            df["volume"] = df["volume"].astype(int)
            result[symbol] = df
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")

    logger.info(f"Successfully fetched {len(result)}/{len(symbols)} symbols")
    return result


def fetch_daily_latest(symbols: list[str], period: str = "5d") -> dict[str, pd.DataFrame]:
    """Fetch latest few days of daily data (for nightly incremental updates)."""
    return fetch_daily(symbols, period=period)


def fetch_intraday(symbols: list[str], interval: str = "15m") -> dict[str, pd.DataFrame]:
    """
    Fetch intraday data for today.
    Returns {symbol: DataFrame} with columns: timestamp, open, high, low, close, volume
    """
    logger.info(f"Fetching intraday ({interval}) for {len(symbols)} symbols")
    tickers_str = " ".join(symbols)
    raw = yf.download(tickers_str, period="1d", interval=interval,
                      auto_adjust=True, group_by="ticker", threads=True)

    result = {}
    for symbol in symbols:
        try:
            # Extract per-symbol data from MultiIndex columns
            if isinstance(raw.columns, pd.MultiIndex):
                if symbol in raw.columns.get_level_values(-1):
                    df = raw.xs(symbol, level="Ticker", axis=1).copy()
                elif len(symbols) == 1:
                    df = raw.droplevel("Ticker", axis=1).copy()
                else:
                    continue
            else:
                df = raw.copy()

            df = df.dropna(subset=["Close"])
            if df.empty:
                continue

            df = df.reset_index()
            # yfinance uses "Datetime" for intraday index
            ts_col = "Datetime" if "Datetime" in df.columns else "Date"
            df = df.rename(columns={
                ts_col: "timestamp",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            })
            df = df[["timestamp", "open", "high", "low", "close", "volume"]]
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df["volume"] = df["volume"].astype(int)
            result[symbol] = df
        except Exception as e:
            logger.error(f"Error processing intraday for {symbol}: {e}")

    logger.info(f"Successfully fetched intraday for {len(result)}/{len(symbols)} symbols")
    return result


def fetch_nifty50_index(period: str = "5d") -> pd.DataFrame | None:
    """Fetch Nifty 50 index data."""
    try:
        df = yf.download("^NSEI", period=period, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df = df.droplevel("Ticker", axis=1)
        df = df.reset_index()
        df = df.rename(columns={"Date": "date", "Close": "close"})
        df["date"] = pd.to_datetime(df["date"]).dt.date
        return df[["date", "close"]]
    except Exception as e:
        logger.error(f"Error fetching Nifty 50 index: {e}")
        return None
