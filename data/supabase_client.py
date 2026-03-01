"""Supabase client with helpers for all table operations."""

from __future__ import annotations
import json
from datetime import date, datetime
from supabase import create_client, Client
from config.settings import SUPABASE_URL, SUPABASE_KEY


def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


_client: Client | None = None


def client() -> Client:
    global _client
    if _client is None:
        _client = get_client()
    return _client


# ── Generic helpers ───────────────────────────────────────────

def upsert(table: str, rows: list[dict], on_conflict: str = "") -> None:
    """Upsert rows into a table. on_conflict is the unique constraint columns."""
    if not rows:
        return
    # Serialize date/datetime objects
    cleaned = []
    for row in rows:
        cleaned.append({
            k: (v.isoformat() if isinstance(v, (date, datetime)) else v)
            for k, v in row.items()
        })
    batch_size = 500
    for i in range(0, len(cleaned), batch_size):
        batch = cleaned[i:i + batch_size]
        q = client().table(table).upsert(batch, on_conflict=on_conflict)
        q.execute()


def insert(table: str, rows: list[dict]) -> None:
    if not rows:
        return
    cleaned = []
    for row in rows:
        cleaned.append({
            k: (v.isoformat() if isinstance(v, (date, datetime)) else v)
            for k, v in row.items()
        })
    batch_size = 500
    for i in range(0, len(cleaned), batch_size):
        batch = cleaned[i:i + batch_size]
        client().table(table).insert(batch).execute()


def query(table: str, select: str = "*", filters: dict | None = None,
          order: str | None = None, limit: int | None = None) -> list[dict]:
    """Simple query builder."""
    q = client().table(table).select(select)
    if filters:
        for col, val in filters.items():
            q = q.eq(col, val)
    if order:
        desc = order.startswith("-")
        col = order.lstrip("-")
        q = q.order(col, desc=desc)
    if limit:
        q = q.limit(limit)
    return q.execute().data


def update(table: str, filters: dict, values: dict) -> None:
    q = client().table(table).update(values)
    for col, val in filters.items():
        q = q.eq(col, val)
    q.execute()


# ── Stock helpers ─────────────────────────────────────────────

def get_stock_id(symbol: str) -> int | None:
    rows = query("stocks", select="id", filters={"symbol": symbol})
    return rows[0]["id"] if rows else None


def get_all_stock_ids() -> dict[str, int]:
    """Returns {symbol: id} mapping."""
    rows = query("stocks", select="id,symbol")
    return {r["symbol"]: r["id"] for r in rows}


def seed_stocks(stock_list: list[dict]) -> None:
    """Insert stock universe into stocks table."""
    rows = []
    for s in stock_list:
        rows.append({
            "symbol": s["symbol"],
            "indianapi_name": s.get("indianapi_name"),
            "company_name": s["company_name"],
            "sector": s.get("sector"),
            "industry": s.get("industry"),
            "market_cap_category": s.get("market_cap_category"),
            "is_nifty50": s.get("is_nifty50", False),
            "is_active": True,
        })
    upsert("stocks", rows, on_conflict="symbol")


# ── Price helpers ─────────────────────────────────────────────

def upsert_daily_prices(stock_id: int, price_rows: list[dict]) -> None:
    rows = [{"stock_id": stock_id, **r} for r in price_rows]
    upsert("daily_prices", rows, on_conflict="stock_id,date")


def upsert_intraday_prices(stock_id: int, price_rows: list[dict]) -> None:
    rows = [{"stock_id": stock_id, **r} for r in price_rows]
    upsert("intraday_prices", rows, on_conflict="stock_id,timestamp")


def get_daily_prices(stock_id: int, days: int = 60) -> list[dict]:
    return query(
        "daily_prices",
        filters={"stock_id": stock_id},
        order="-date",
        limit=days,
    )


# ── Technical indicators ─────────────────────────────────────

def upsert_indicators(stock_id: int, indicator_rows: list[dict]) -> None:
    rows = [{"stock_id": stock_id, **r} for r in indicator_rows]
    upsert("technical_indicators", rows, on_conflict="stock_id,date")


# ── Sentiment ─────────────────────────────────────────────────

def upsert_sentiment(stock_id: int, sentiment_row: dict) -> None:
    row = {"stock_id": stock_id, **sentiment_row}
    upsert("sentiment_scores", [row], on_conflict="stock_id,date")


# ── Analyst data ──────────────────────────────────────────────

def upsert_analyst(stock_id: int, analyst_row: dict) -> None:
    row = {"stock_id": stock_id, **analyst_row}
    upsert("analyst_data", [row], on_conflict="stock_id,date")


# ── Market context ────────────────────────────────────────────

def upsert_market_context(context_row: dict) -> None:
    # Serialize any nested dicts/lists to JSON strings for JSONB columns
    for key in ["top_gainers", "top_losers", "price_shockers",
                "most_active_nse", "week_52_highs", "week_52_lows", "commodities"]:
        if key in context_row and not isinstance(context_row[key], str):
            context_row[key] = json.dumps(context_row[key])
    upsert("market_context", [context_row], on_conflict="date")


# ── Predictions ───────────────────────────────────────────────

def insert_predictions(predictions: list[dict]) -> None:
    insert("predictions", predictions)


def update_prediction_outcome(prediction_id: int, actual_direction: str,
                               actual_pct_change: float, was_correct: bool) -> None:
    update("predictions", {"id": prediction_id}, {
        "actual_direction": actual_direction,
        "actual_pct_change": actual_pct_change,
        "was_correct": was_correct,
    })


def get_pending_predictions(prediction_type: str = "nightly") -> list[dict]:
    """Get predictions that don't have outcomes yet."""
    rows = client().table("predictions") \
        .select("*") \
        .eq("prediction_type", prediction_type) \
        .is_("was_correct", "null") \
        .order("prediction_timestamp", desc=True) \
        .limit(200) \
        .execute().data
    return rows


# ── Model performance ─────────────────────────────────────────

def upsert_model_performance(perf_row: dict) -> None:
    upsert("model_performance", [perf_row],
           on_conflict="model_version,evaluation_date,prediction_type")


# ── API call log ──────────────────────────────────────────────

def log_api_call(endpoint: str, params: dict | None, status_code: int) -> None:
    insert("api_call_log", [{
        "endpoint": endpoint,
        "params": json.dumps(params) if params else None,
        "status_code": status_code,
    }])


def get_api_calls_this_month() -> int:
    now = datetime.utcnow()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = client().table("api_call_log") \
        .select("id", count="exact") \
        .gte("called_at", start.isoformat()) \
        .execute()
    return rows.count or 0


# ── Pipeline runs ─────────────────────────────────────────────

def log_pipeline_start(pipeline_name: str) -> int:
    result = client().table("pipeline_runs").insert({
        "pipeline_name": pipeline_name,
        "status": "running",
    }).execute()
    return result.data[0]["id"]


def log_pipeline_end(run_id: int, status: str, details: dict | None = None,
                     error: str | None = None) -> None:
    update("pipeline_runs", {"id": run_id}, {
        "status": status,
        "finished_at": datetime.utcnow().isoformat(),
        "details": json.dumps(details) if details else None,
        "error_message": error,
    })


# ── Model storage (Supabase Storage) ─────────────────────────

def _local_model_dir():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent / "models" / "saved"


def upload_model(model_bytes: bytes, version: str) -> None:
    """Upload model pickle to Supabase Storage, fallback to local disk."""
    path = f"{version}.pkl"
    try:
        client().storage.from_("models").upload(path, model_bytes,
                                                 file_options={"content-type": "application/octet-stream",
                                                               "upsert": "true"})
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Supabase Storage upload failed ({e}), saving locally")
        _local_model_dir().mkdir(parents=True, exist_ok=True)
        (_local_model_dir() / path).write_bytes(model_bytes)


def download_model(version: str) -> bytes:
    """Download model pickle from Supabase Storage, fallback to local disk."""
    path = f"{version}.pkl"
    local = _local_model_dir() / path
    if local.exists():
        return local.read_bytes()
    return client().storage.from_("models").download(path)


def get_latest_model_version() -> str | None:
    """Get the latest model version from model_performance table."""
    rows = query("model_performance", select="model_version",
                 order="-evaluation_date", limit=1)
    return rows[0]["model_version"] if rows else None
