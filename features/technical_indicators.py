"""Compute technical indicators from OHLCV data using pure numpy/pandas."""

from __future__ import annotations
import pandas as pd
import numpy as np


def _rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False, min_periods=length).mean()


def _sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(window=length, min_periods=length).mean()


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = _ema(series, fast)
    ema_slow = _ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _bbands(series: pd.Series, length: int = 20, std: float = 2.0):
    mid = _sma(series, length)
    rolling_std = series.rolling(window=length, min_periods=length).std()
    upper = mid + std * rolling_std
    lower = mid - std * rolling_std
    return lower, mid, upper


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / length, min_periods=length).mean()


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff())
    direction.iloc[0] = 0
    return (volume * direction).cumsum()


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
    atr = _atr(high, low, close, length)
    plus_di = 100 * _ema(plus_dm, length) / atr.replace(0, np.nan)
    minus_di = 100 * _ema(minus_dm, length) / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return _ema(dx, length)


def _stoch(high: pd.Series, low: pd.Series, close: pd.Series,
           k_period: int = 14, d_period: int = 3):
    lowest_low = low.rolling(window=k_period, min_periods=k_period).min()
    highest_high = high.rolling(window=k_period, min_periods=k_period).max()
    denom = (highest_high - lowest_low).replace(0, np.nan)
    stoch_k = 100 * (close - lowest_low) / denom
    stoch_d = _sma(stoch_k, d_period)
    return stoch_k, stoch_d


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """
    Given a DataFrame with columns [date, open, high, low, close, volume],
    compute all technical indicators and return a DataFrame with one row per date.
    Expects at least 60 rows for reliable indicator computation.
    """
    df = df.sort_values("date").reset_index(drop=True)

    result = pd.DataFrame()
    result["date"] = df["date"]

    # RSI
    result["rsi_14"] = _rsi(df["close"], 14)

    # MACD
    macd_line, signal_line, histogram = _macd(df["close"])
    result["macd"] = macd_line
    result["macd_signal"] = signal_line
    result["macd_hist"] = histogram

    # Bollinger Bands
    bb_lower, bb_mid, bb_upper = _bbands(df["close"])
    result["bb_upper"] = bb_upper
    result["bb_middle"] = bb_mid
    result["bb_lower"] = bb_lower

    # ATR
    result["atr_14"] = _atr(df["high"], df["low"], df["close"], 14)

    # OBV
    result["obv"] = _obv(df["close"], df["volume"])

    # Simple Moving Averages
    result["sma_20"] = _sma(df["close"], 20)
    result["sma_50"] = _sma(df["close"], 50)

    # Exponential Moving Averages
    result["ema_12"] = _ema(df["close"], 12)
    result["ema_26"] = _ema(df["close"], 26)

    # ADX
    result["adx_14"] = _adx(df["high"], df["low"], df["close"], 14)

    # Stochastic
    stoch_k, stoch_d = _stoch(df["high"], df["low"], df["close"])
    result["stoch_k"] = stoch_k
    result["stoch_d"] = stoch_d

    # VWAP (approximate using typical price * volume)
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cum_vol = df["volume"].cumsum()
    cum_tp_vol = (typical_price * df["volume"]).cumsum()
    result["vwap"] = cum_tp_vol / cum_vol.replace(0, np.nan)

    # Percentage changes (momentum)
    result["pct_change_1d"] = df["close"].pct_change(1)
    result["pct_change_5d"] = df["close"].pct_change(5)
    result["pct_change_20d"] = df["close"].pct_change(20)

    # Volatility (20-day rolling std of returns)
    result["volatility_20d"] = df["close"].pct_change(1).rolling(20).std()

    return result


def compute_ml_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute ML-ready features from OHLCV data.
    All features are normalized/ratio-based (not raw price levels).
    Designed for cross-stock training compatibility.
    """
    df = df.sort_values("date").reset_index(drop=True)
    indicators = compute_all(df)
    close = df["close"]

    features = pd.DataFrame()
    features["date"] = indicators["date"]

    # --- Bounded oscillators (already normalized) ---
    features["rsi_14"] = indicators["rsi_14"]
    features["adx_14"] = indicators["adx_14"]
    features["stoch_k"] = indicators["stoch_k"]
    features["stoch_d"] = indicators["stoch_d"]

    # --- MACD normalized by price (not raw rupee difference) ---
    features["macd_pct"] = (indicators["macd"] / close) * 100
    features["macd_signal_pct"] = (indicators["macd_signal"] / close) * 100
    features["macd_hist_pct"] = (indicators["macd_hist"] / close) * 100

    # --- ATR normalized by price (volatility as % of price) ---
    features["atr_pct"] = (indicators["atr_14"] / close) * 100

    # --- Bollinger Band position (0=lower, 1=upper) ---
    bb_range = indicators["bb_upper"] - indicators["bb_lower"]
    features["bb_position"] = (
        (close - indicators["bb_lower"]) / bb_range.replace(0, np.nan)
    )
    # BB width normalized
    features["bb_width"] = bb_range / indicators["bb_middle"].replace(0, np.nan)

    # --- Distance from moving averages (normalized %) ---
    features["sma_20_distance"] = (close - indicators["sma_20"]) / indicators["sma_20"]
    features["sma_50_distance"] = (close - indicators["sma_50"]) / indicators["sma_50"]

    # --- EMA crossover signal ---
    ema_diff = indicators["ema_12"] - indicators["ema_26"]
    ema_diff_prev = ema_diff.shift(1)
    features["ema_crossover"] = np.where(
        (ema_diff > 0) & (ema_diff_prev <= 0), 1,
        np.where((ema_diff < 0) & (ema_diff_prev >= 0), -1, 0)
    )
    # EMA spread normalized
    features["ema_spread_pct"] = (ema_diff / close) * 100

    # --- Momentum at multiple horizons ---
    features["pct_change_1d"] = close.pct_change(1)
    features["pct_change_5d"] = close.pct_change(5)
    features["momentum_10d"] = close.pct_change(10)
    features["pct_change_20d"] = close.pct_change(20)
    features["momentum_63d"] = close.pct_change(63)  # ~3 months

    # Short-term reversal (contrarian 1-day)
    features["return_reversal_1d"] = -close.pct_change(1)

    # --- Volatility ---
    daily_ret = close.pct_change(1)
    features["volatility_5d"] = daily_ret.rolling(5).std()
    features["volatility_20d"] = daily_ret.rolling(20).std()
    features["volatility_ratio"] = (
        daily_ret.rolling(5).std() / daily_ret.rolling(20).std().replace(0, np.nan)
    )

    # Garman-Klass volatility (better than close-to-close)
    log_hl = np.log(df["high"] / df["low"].replace(0, np.nan)) ** 2
    log_co = np.log(close / df["open"].replace(0, np.nan)) ** 2
    features["gk_volatility"] = np.sqrt(
        (0.5 * log_hl - (2 * np.log(2) - 1) * log_co).rolling(20).mean()
    )

    # --- Volume features ---
    vol_avg_20 = df["volume"].rolling(20).mean()
    vol_avg_50 = df["volume"].rolling(50).mean()
    features["volume_ratio"] = df["volume"] / vol_avg_20.replace(0, np.nan)
    features["volume_ratio_50d"] = df["volume"] / vol_avg_50.replace(0, np.nan)
    features["volume_trend_5d"] = df["volume"].pct_change(5)

    # OBV rate of change (not raw cumulative OBV)
    obv = indicators["obv"]
    features["obv_roc_5d"] = obv.pct_change(5)
    features["obv_roc_20d"] = obv.pct_change(20)

    # --- Price position features ---
    # 52-week (252 trading days) high/low position
    high_52w = df["high"].rolling(252, min_periods=60).max()
    low_52w = df["low"].rolling(252, min_periods=60).min()
    range_52w = (high_52w - low_52w).replace(0, np.nan)
    features["price_52w_position"] = (close - low_52w) / range_52w

    # Distance from 52-week high
    features["dist_from_52w_high"] = (close - high_52w) / high_52w

    # --- Candle pattern features ---
    body = (close - df["open"]).abs()
    wick_total = (df["high"] - df["low"]).replace(0, np.nan)
    features["candle_body_ratio"] = body / wick_total
    # Direction of candle (bullish/bearish)
    features["candle_direction"] = np.sign(close - df["open"])

    # Gap percentage (open vs previous close)
    features["gap_pct"] = (df["open"] - close.shift(1)) / close.shift(1)

    # High-low range normalized
    features["high_low_range"] = (df["high"] - df["low"]) / close

    # --- VWAP distance (normalized) ---
    typical_price = (df["high"] + df["low"] + close) / 3
    cum_vol = df["volume"].cumsum()
    cum_tp_vol = (typical_price * df["volume"]).cumsum()
    vwap = cum_tp_vol / cum_vol.replace(0, np.nan)
    features["vwap_distance"] = (close - vwap) / vwap.replace(0, np.nan)

    # --- Leading indicators (change BEFORE price turns) ---

    # Momentum acceleration: rate of change of momentum
    # If momentum is decelerating, price turn is coming
    mom_5d = close.pct_change(5)
    features["momentum_accel_5d"] = mom_5d - mom_5d.shift(5)  # momentum change
    mom_10d = close.pct_change(10)
    features["momentum_accel_10d"] = mom_10d - mom_10d.shift(5)

    # RSI rate of change (RSI turning before price does)
    rsi = indicators["rsi_14"]
    features["rsi_roc_5d"] = rsi - rsi.shift(5)

    # RSI-price divergence: price making new highs but RSI isn't (bearish)
    # or price making new lows but RSI isn't (bullish)
    price_5d_high = close.rolling(5).max() == close  # price at 5d high
    rsi_5d_high = rsi.rolling(5).max() == rsi  # RSI at 5d high
    features["rsi_price_divergence"] = (
        price_5d_high.astype(float) - rsi_5d_high.astype(float)
    )  # +1 = bearish divergence, -1 = bullish divergence

    # MACD histogram slope (trend weakening before price turns)
    macd_hist = indicators["macd_hist"]
    features["macd_hist_slope"] = macd_hist - macd_hist.shift(1)
    features["macd_hist_accel"] = features["macd_hist_slope"] - features["macd_hist_slope"].shift(1)

    # Volume-price divergence: price rising but volume falling = weak rally
    vol_5d_avg = df["volume"].rolling(5).mean()
    vol_10d_avg = df["volume"].rolling(10).mean()
    features["volume_price_diverge"] = (
        mom_5d * np.sign(vol_5d_avg - vol_10d_avg)
    )  # negative = price up but volume declining (or vice versa)

    # Bollinger Band squeeze (low volatility precedes big moves)
    features["bb_squeeze"] = features["bb_width"].rolling(20).rank(pct=True)

    # Mean reversion signal: distance from 20d SMA (extreme = likely to revert)
    features["mean_reversion_20d"] = -features["sma_20_distance"]  # flip sign

    return features
