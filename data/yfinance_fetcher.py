"""Fetch stock data from yfinance (free, no API key needed)."""

from __future__ import annotations
import logging
import time
from datetime import date
import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)

BATCH_SIZE = 10      # symbols per request
BATCH_DELAY = 3.0    # seconds between batches to avoid rate limiting


def _download_batched(symbols: list[str], **kwargs) -> pd.DataFrame:
    """Download in small batches with delays to avoid Yahoo rate limiting."""
    frames = []
    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        try:
            raw = yf.download(" ".join(batch), group_by="ticker",
                              threads=False, **kwargs)
            frames.append((batch, raw))
        except Exception as e:
            logger.warning(f"Batch {i//BATCH_SIZE + 1} failed: {e}")
        if i + BATCH_SIZE < len(symbols):
            time.sleep(BATCH_DELAY)
    return frames


def fetch_daily(symbols: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
    """
    Fetch daily OHLCV for multiple symbols.
    Returns {symbol: DataFrame} with columns: date, open, high, low, close, volume
    """
    logger.info(f"Fetching daily data for {len(symbols)} symbols, period={period}")
    batches = _download_batched(symbols, period=period, auto_adjust=True)

    result = {}
    for batch_symbols, raw in batches:
        for symbol in batch_symbols:
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    if symbol in raw.columns.get_level_values(-1):
                        df = raw.xs(symbol, level="Ticker", axis=1).copy()
                    elif len(batch_symbols) == 1:
                        df = raw.droplevel("Ticker", axis=1).copy()
                    else:
                        continue
                else:
                    df = raw.copy()

                df = df.dropna(subset=["Close"])
                if df.empty:
                    continue

                df = df.reset_index()
                df = df.rename(columns={
                    "Date": "date", "Open": "open", "High": "high",
                    "Low": "low", "Close": "close", "Volume": "volume",
                })
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
    batches = _download_batched(symbols, period="1d", interval=interval,
                                auto_adjust=True)

    result = {}
    for batch_symbols, raw in batches:
        for symbol in batch_symbols:
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    if symbol in raw.columns.get_level_values(-1):
                        df = raw.xs(symbol, level="Ticker", axis=1).copy()
                    elif len(batch_symbols) == 1:
                        df = raw.droplevel("Ticker", axis=1).copy()
                    else:
                        continue
                else:
                    df = raw.copy()

                df = df.dropna(subset=["Close"])
                if df.empty:
                    continue

                df = df.reset_index()
                ts_col = "Datetime" if "Datetime" in df.columns else "Date"
                df = df.rename(columns={
                    ts_col: "timestamp", "Open": "open", "High": "high",
                    "Low": "low", "Close": "close", "Volume": "volume",
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
