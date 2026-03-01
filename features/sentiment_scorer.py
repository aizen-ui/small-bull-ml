"""
Sentiment analysis for stock news headlines.
Uses a hybrid approach: financial dictionary + TextBlob + keyword amplifiers.
Designed to be fast enough for GitHub Actions (no GPU needed).
"""

from __future__ import annotations
import math
import re
from datetime import datetime
from textblob import TextBlob

# ── Loughran-McDonald Financial Sentiment Words (curated subset) ──

POSITIVE_WORDS = {
    "achieve", "advancement", "benefit", "beneficial", "best", "boost",
    "breakthrough", "bullish", "confident", "creative", "dividend",
    "earnings", "efficient", "enhance", "exceeded", "excellent",
    "expansion", "favorable", "gain", "good", "great", "grew", "growth",
    "higher", "improve", "improved", "improvement", "increase", "increased",
    "innovative", "leader", "leading", "opportunities", "opportunity",
    "optimal", "optimistic", "outperform", "positive", "profit",
    "profitable", "progress", "prosper", "rally", "record", "recover",
    "recovery", "revenue", "rise", "rising", "robust", "soar", "solid",
    "strength", "strong", "succeed", "success", "successful", "surge",
    "surpass", "top", "upbeat", "upgrade", "upturn", "win",
}

NEGATIVE_WORDS = {
    "adverse", "bankrupt", "bankruptcy", "bearish", "caution", "close",
    "closure", "concern", "crisis", "cut", "danger", "debt", "decline",
    "declined", "declining", "default", "deficit", "delay", "deteriorate",
    "disappoint", "disappointed", "disappointing", "downturn", "downgrade",
    "drop", "dropped", "fail", "failed", "failure", "fall", "falling",
    "fear", "fraud", "investigation", "layoff", "litigation", "lose",
    "loss", "losses", "lower", "miss", "missed", "negative", "penalty",
    "plunge", "poor", "problem", "recession", "restructure", "risk",
    "scandal", "sebi", "sell", "selloff", "shortage", "shrink", "slump",
    "struggle", "suspend", "threat", "trouble", "uncertain", "unfavorable",
    "volatile", "warn", "warning", "weak", "weakness", "worsen", "worst",
}

# ── Keyword Amplifier Patterns ────────────────────────────────

STRONG_POSITIVE_PATTERNS = [
    r"\bbuyback\b", r"\bstock split\b", r"\bbonus\b", r"\bdividend\b",
    r"\bbeat estimates\b", r"\brecord revenue\b", r"\brecord profit\b",
    r"\bupgrade[ds]?\b", r"\brating upgrade\b", r"\btarget raised\b",
    r"\bstrong results\b", r"\bexpansion plan\b", r"\bnew order[s]?\b",
    r"\bcontract win\b", r"\bacquisition\b",
]

STRONG_NEGATIVE_PATTERNS = [
    r"\bfraud\b", r"\bscam\b", r"\bsebi penalty\b", r"\bsebi order\b",
    r"\bdefault\b", r"\bdowngrade[ds]?\b", r"\bloss widen\b",
    r"\bmiss estimates\b", r"\bprofit warning\b", r"\bdebt crisis\b",
    r"\blayoffs?\b", r"\bbank(?:rupt(?:cy)?)\b", r"\bsuspend(?:ed)?\b",
    r"\binvestigation\b", r"\braid\b", r"\barrest\b",
    r"\btarget cut\b", r"\brating downgrade\b",
]


def _loughran_mcdonald_score(text: str) -> float:
    """Score using financial sentiment dictionary."""
    words = text.lower().split()
    if not words:
        return 0.0
    pos = sum(1 for w in words if w in POSITIVE_WORDS)
    neg = sum(1 for w in words if w in NEGATIVE_WORDS)
    total = len(words)
    return (pos - neg) / total


def _textblob_score(text: str) -> float:
    """General sentiment via TextBlob."""
    return TextBlob(text).sentiment.polarity


def _keyword_amplified_score(text: str) -> float:
    """Check for strong signal keywords, return amplified score."""
    text_lower = text.lower()
    pos_hits = sum(1 for p in STRONG_POSITIVE_PATTERNS if re.search(p, text_lower))
    neg_hits = sum(1 for p in STRONG_NEGATIVE_PATTERNS if re.search(p, text_lower))

    if pos_hits == 0 and neg_hits == 0:
        return 0.0

    base = (pos_hits - neg_hits) / max(pos_hits + neg_hits, 1)
    return base * 1.5  # amplification factor


def score_headline(text: str) -> float:
    """
    Score a single headline. Returns value in [-1.0, 1.0].
    Combines three scoring methods.
    """
    lm = _loughran_mcdonald_score(text)
    tb = _textblob_score(text)
    kw = _keyword_amplified_score(text)

    combined = 0.4 * lm + 0.3 * tb + 0.3 * kw
    return max(-1.0, min(1.0, combined))


def score_news_batch(headlines: list[dict]) -> dict:
    """
    Score a batch of news items for a single stock.

    Args:
        headlines: List of dicts, each with at least a "title" key.
                   Optional "timestamp" key for recency weighting.

    Returns:
        dict with: avg_sentiment, max_sentiment, min_sentiment,
                   weighted_sentiment, news_count
    """
    if not headlines:
        return {
            "avg_sentiment": 0.0,
            "max_sentiment": 0.0,
            "min_sentiment": 0.0,
            "weighted_sentiment": 0.0,
            "news_count": 0,
        }

    scores = []
    weights = []
    now = datetime.utcnow()

    for item in headlines:
        title = item.get("title") or item.get("headline") or ""
        if not title:
            continue

        score = score_headline(title)
        scores.append(score)

        # Recency weight
        ts = item.get("timestamp") or item.get("date")
        if ts:
            try:
                if isinstance(ts, str):
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                else:
                    dt = ts
                days_old = max(0, (now - dt.replace(tzinfo=None)).days)
                weight = math.exp(-0.3 * days_old)
            except Exception:
                weight = 0.5
        else:
            weight = 0.5  # unknown date gets medium weight

        weights.append(weight)

    if not scores:
        return {
            "avg_sentiment": 0.0,
            "max_sentiment": 0.0,
            "min_sentiment": 0.0,
            "weighted_sentiment": 0.0,
            "news_count": 0,
        }

    total_weight = sum(weights) or 1.0
    weighted_sentiment = sum(s * w for s, w in zip(scores, weights)) / total_weight

    return {
        "avg_sentiment": round(sum(scores) / len(scores), 4),
        "max_sentiment": round(max(scores), 4),
        "min_sentiment": round(min(scores), 4),
        "weighted_sentiment": round(weighted_sentiment, 4),
        "news_count": len(scores),
    }
