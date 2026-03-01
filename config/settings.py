import os
from dotenv import load_dotenv

load_dotenv()

# Supabase
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

# IndianAPI
INDIANAPI_KEY = os.environ["INDIANAPI_KEY"]
INDIANAPI_BASE_URL = "https://stock-market-api.indianapi.in"
INDIANAPI_MONTHLY_LIMIT = 500
INDIANAPI_DAILY_STOCK_CALLS = 10  # rotate 10 stocks/day for /stock endpoint
INDIANAPI_WEEKLY_TARGET_CALLS = 10  # /stock_target_price per week

# yfinance
YFINANCE_HISTORY_YEARS = 10  # how far back for initial backfill
YFINANCE_DAILY_PERIOD = "5d"  # nightly incremental fetch
YFINANCE_INTRADAY_INTERVAL = "1m"  # 1-minute bars for minute-level predictions

# ML
TRAIN_TEST_SPLIT = 0.8  # temporal split
NEUTRAL_THRESHOLD = 0.001  # +/-0.1% = neutral
MODEL_STORAGE_BUCKET = "models"

# Trading calendar
MARKET_OPEN_HOUR = 9   # IST
MARKET_OPEN_MINUTE = 15
MARKET_CLOSE_HOUR = 15  # IST
MARKET_CLOSE_MINUTE = 30

# Indian market holidays 2026 (update annually)
MARKET_HOLIDAYS = [
    "2026-01-26",  # Republic Day
    "2026-03-10",  # Maha Shivaratri
    "2026-03-17",  # Holi
    "2026-03-31",  # Id-Ul-Fitr
    "2026-04-02",  # Ram Navami
    "2026-04-03",  # Mahavir Jayanti
    "2026-04-14",  # Dr. Ambedkar Jayanti
    "2026-04-18",  # Good Friday
    "2026-05-01",  # Maharashtra Day
    "2026-05-25",  # Buddha Purnima
    "2026-06-07",  # Bakri Id
    "2026-07-07",  # Muharram
    "2026-08-15",  # Independence Day
    "2026-08-16",  # Parsi New Year
    "2026-09-05",  # Milad-Un-Nabi
    "2026-10-02",  # Mahatma Gandhi Jayanti
    "2026-10-21",  # Dussehra
    "2026-11-04",  # Diwali - Laxmi Pujan
    "2026-11-05",  # Diwali - Balipratipada
    "2026-11-19",  # Guru Nanak Jayanti
    "2026-12-25",  # Christmas
]
