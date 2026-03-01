"""
Fundamentals Feature Extractor
Converts Screener.in / Excel financial data into ML-ready features.
These features capture company performance, financial health, and growth trends.
"""

import logging
import os
import numpy as np
import pandas as pd
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Directory where uploaded xlsx files are stored
UPLOADS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "uploads"
)


def _parse_data_sheet(filepath: str) -> Dict[str, Dict]:
    """
    Parse the Screener.in Data Sheet directly.
    The Data Sheet contains ALL financial data in sections:
      - PROFIT & LOSS (rows after 'PROFIT & LOSS' header)
      - BALANCE SHEET (rows after 'BALANCE SHEET' header)
      - CASH FLOW: (rows after 'CASH FLOW:' header)
    Each section has a 'Report Date' row with datetime columns,
    followed by metric rows with values in the same columns.

    Returns dict with keys: 'pl', 'bs', 'cf' each being a dict of
    {metric_name: {year_index: value}}, plus 'years' and 'company_info'.
    """
    xl = pd.ExcelFile(filepath)
    if "Data Sheet" not in xl.sheet_names:
        return {}

    df = pd.read_excel(xl, sheet_name="Data Sheet", header=None)
    result = {"pl": {}, "bs": {}, "cf": {}, "years": {}, "company_info": {}}

    # Company info
    for i in range(min(12, len(df))):
        label = str(df.iloc[i, 0]).strip() if pd.notna(df.iloc[i, 0]) else ""
        val = df.iloc[i, 1] if df.shape[1] > 1 and pd.notna(df.iloc[i, 1]) else None
        if "COMPANY NAME" in label.upper():
            result["company_info"]["name"] = val
        elif "Current Price" in label:
            result["company_info"]["price"] = float(val) if val else 0
        elif "Market Capitalization" in label:
            result["company_info"]["market_cap"] = float(val) if val else 0

    # Find section start rows
    sections = {}
    for i in range(len(df)):
        cell = str(df.iloc[i, 0]).strip() if pd.notna(df.iloc[i, 0]) else ""
        if cell == "PROFIT & LOSS":
            sections["pl"] = i
        elif cell == "BALANCE SHEET":
            sections["bs"] = i
        elif cell.startswith("CASH FLOW"):
            sections["cf"] = i

    def _parse_section(start_row: int, end_row: int) -> tuple:
        """Parse a section, returning (data_dict, year_columns)."""
        data = {}
        year_cols = []

        for i in range(start_row + 1, end_row):
            label = str(df.iloc[i, 0]).strip() if pd.notna(df.iloc[i, 0]) else ""
            if not label:
                continue

            if label == "Report Date":
                # Find columns with datetime values
                for j in range(1, df.shape[1]):
                    val = df.iloc[i, j]
                    if pd.notna(val):
                        year_cols.append(j)
                continue

            if not year_cols:
                continue

            # Extract values for this metric across all year columns
            values = {}
            for j in year_cols:
                val = df.iloc[i, j]
                if pd.notna(val):
                    try:
                        values[j] = float(val)
                    except (ValueError, TypeError):
                        pass

            if values:
                data[label] = values

        return data, year_cols

    # Determine section boundaries
    section_order = sorted(sections.items(), key=lambda x: x[1])
    for idx, (name, start) in enumerate(section_order):
        if idx + 1 < len(section_order):
            end = section_order[idx + 1][1]
        else:
            end = len(df)
        result[name], year_cols = _parse_section(start, end)
        if year_cols and not result["years"]:
            result["years"] = year_cols

    return result


def extract_fundamentals_features(filepath: str) -> Dict[str, float]:
    """
    Parse a Screener.in xlsx and extract fundamental features for ML.
    Reads directly from the Data Sheet which contains all financial data.

    Returns dict of feature_name -> value (latest year).
    """
    try:
        parsed = _parse_data_sheet(filepath)
    except Exception as e:
        logger.warning(f"Failed to parse Data Sheet from {filepath}: {e}")
        return {}

    if not parsed or not parsed.get("years"):
        logger.warning(f"No year columns found in {filepath}")
        return {}

    pl = parsed["pl"]
    bs = parsed["bs"]
    cf = parsed["cf"]
    year_cols = parsed["years"]  # list of column indices

    # Latest and previous year column indices
    latest = year_cols[-1]
    prev = year_cols[-2] if len(year_cols) >= 2 else None
    first = year_cols[0] if len(year_cols) >= 3 else None

    def _get(section: dict, metric: str, year_col=None) -> float:
        """Get a metric value, with partial-match fallback."""
        yc = year_col or latest
        # Exact match
        if metric in section:
            return section[metric].get(yc, np.nan)
        # Partial case-insensitive match
        metric_lower = metric.lower()
        for key in section:
            if metric_lower in key.lower():
                return section[key].get(yc, np.nan)
        return np.nan

    def _div(a, b):
        if pd.isna(a) or pd.isna(b) or b == 0:
            return np.nan
        return a / b

    features = {}

    # --- P&L metrics ---
    sales = _get(pl, "Sales")
    net_profit = _get(pl, "Net profit")
    operating_profit = _get(pl, "Operating Profit")
    # If no explicit Operating Profit in P&L section, derive from Sales - Expenses
    if pd.isna(operating_profit):
        expenses = _get(pl, "Expenses")
        if not pd.isna(sales) and not pd.isna(expenses):
            operating_profit = sales - expenses
    depreciation = _get(pl, "Depreciation")
    interest = _get(pl, "Interest")

    ebitda = (operating_profit + depreciation) if not pd.isna(operating_profit) and not pd.isna(depreciation) else np.nan
    # Gross profit = Sales - (Expenses - Depreciation - Interest)
    expenses = _get(pl, "Expenses")
    if pd.isna(expenses):
        # Sum individual expense items
        raw_mat = _get(pl, "Raw Material Cost")
        emp_cost = _get(pl, "Employee Cost")
        other_exp = _get(pl, "Other Expenses")
        selling = _get(pl, "Selling and admin")
        expenses_items = [raw_mat, emp_cost, other_exp, selling]
        non_nan = [x for x in expenses_items if not pd.isna(x)]
        expenses = sum(non_nan) if non_nan else np.nan

    gross_profit = np.nan
    if not pd.isna(sales) and not pd.isna(expenses) and not pd.isna(depreciation) and not pd.isna(interest):
        direct_costs = expenses - depreciation - interest
        gross_profit = sales - direct_costs

    features["f_net_profit_margin"] = _div(net_profit, sales)
    features["f_operating_margin"] = _div(operating_profit, sales)
    features["f_ebitda_margin"] = _div(ebitda, sales)
    features["f_gross_margin"] = _div(gross_profit, sales)

    # --- Balance Sheet ---
    equity_capital = _get(bs, "Equity Share Capital")
    reserves = _get(bs, "Reserves")
    total_equity = (equity_capital + reserves) if not pd.isna(equity_capital) and not pd.isna(reserves) else np.nan
    borrowings = _get(bs, "Borrowings")
    other_liabilities = _get(bs, "Other Liabilities")
    total_row = _get(bs, "Total")  # Total Assets
    receivables = _get(bs, "Receivables")
    if pd.isna(receivables):
        receivables = _get(bs, "Debtors")
    inventory = _get(bs, "Inventory")
    cash = _get(bs, "Cash & Bank")

    # Current assets = Receivables + Inventory + Cash
    current_assets_parts = [x for x in [receivables, inventory, cash] if not pd.isna(x)]
    current_assets = sum(current_assets_parts) if current_assets_parts else np.nan
    current_liabilities = other_liabilities  # approximation

    features["f_debt_to_equity"] = _div(borrowings, total_equity)
    features["f_debt_to_assets"] = _div(borrowings, total_row)

    features["f_current_ratio"] = _div(current_assets, current_liabilities)
    if not pd.isna(current_assets) and not pd.isna(inventory):
        features["f_quick_ratio"] = _div(current_assets - inventory, current_liabilities)
    else:
        features["f_quick_ratio"] = np.nan

    features["f_asset_turnover"] = _div(sales, total_row)
    features["f_roe"] = _div(net_profit, total_equity)
    features["f_roa"] = _div(net_profit, total_row)

    # --- Cash Flow ---
    ocf = _get(cf, "Cash from Operating Activity")
    icf = _get(cf, "Cash from Investing Activity")
    fcf = (ocf + icf) if not pd.isna(ocf) and not pd.isna(icf) else np.nan

    features["f_ocf_to_revenue"] = _div(ocf, sales)
    features["f_fcf_to_revenue"] = _div(fcf, sales)
    features["f_ocf_to_net_income"] = _div(ocf, net_profit)

    # --- Growth ---
    if prev is not None:
        prev_sales = _get(pl, "Sales", prev)
        prev_profit = _get(pl, "Net profit", prev)
        features["f_revenue_growth_yoy"] = _div(sales - prev_sales, abs(prev_sales)) if not pd.isna(prev_sales) and prev_sales != 0 else np.nan
        features["f_profit_growth_yoy"] = _div(net_profit - prev_profit, abs(prev_profit)) if not pd.isna(prev_profit) and prev_profit != 0 else np.nan
    else:
        features["f_revenue_growth_yoy"] = np.nan
        features["f_profit_growth_yoy"] = np.nan

    if first is not None:
        first_sales = _get(pl, "Sales", first)
        first_profit = _get(pl, "Net profit", first)
        n_years = len(year_cols) - 1
        if not pd.isna(first_sales) and first_sales > 0 and not pd.isna(sales) and sales > 0:
            features["f_revenue_cagr"] = (sales / first_sales) ** (1 / n_years) - 1
        else:
            features["f_revenue_cagr"] = np.nan
        if not pd.isna(first_profit) and first_profit > 0 and not pd.isna(net_profit) and net_profit > 0:
            features["f_profit_cagr"] = (net_profit / first_profit) ** (1 / n_years) - 1
        else:
            features["f_profit_cagr"] = np.nan
    else:
        features["f_revenue_cagr"] = np.nan
        features["f_profit_cagr"] = np.nan

    # --- Interest coverage & EPS ---
    features["f_interest_coverage"] = _div(operating_profit, interest)

    eps = _get(pl, "EPS")
    features["f_eps"] = eps if not pd.isna(eps) else np.nan

    # Replace inf with nan
    for k, v in features.items():
        if isinstance(v, float) and np.isinf(v):
            features[k] = np.nan

    return features


def get_fundamentals_for_stock(symbol: str) -> Dict[str, float]:
    """
    Look for an uploaded xlsx for a given stock symbol and extract features.
    Checks uploads/ directory for files matching the symbol.
    """
    if not os.path.isdir(UPLOADS_DIR):
        return {}

    # Look for matching xlsx files
    clean_symbol = symbol.replace(".NS", "").replace(".BO", "").upper()

    for fname in os.listdir(UPLOADS_DIR):
        if not fname.endswith((".xlsx", ".xls")):
            continue
        # Match by symbol in filename
        fname_upper = fname.upper().replace(" ", "").replace("_", "").replace("-", "")
        if clean_symbol in fname_upper:
            filepath = os.path.join(UPLOADS_DIR, fname)
            logger.info(f"Found xlsx for {symbol}: {fname}")
            return extract_fundamentals_features(filepath)

    return {}


def get_all_fundamentals() -> Dict[str, Dict[str, float]]:
    """
    Scan uploads/ directory and extract fundamentals for all available xlsx files.
    Returns {symbol_hint: features_dict}.
    """
    if not os.path.isdir(UPLOADS_DIR):
        return {}

    result = {}
    for fname in os.listdir(UPLOADS_DIR):
        if not fname.endswith((".xlsx", ".xls")):
            continue
        # Use filename (without ext) as key
        key = os.path.splitext(fname)[0]
        filepath = os.path.join(UPLOADS_DIR, fname)
        try:
            features = extract_fundamentals_features(filepath)
            if features:
                result[key] = features
        except Exception as e:
            logger.warning(f"Error extracting fundamentals from {fname}: {e}")

    return result


# All fundamental feature column names (for consistent feature matrix)
FUNDAMENTAL_FEATURE_COLS = [
    "f_net_profit_margin", "f_operating_margin", "f_ebitda_margin", "f_gross_margin",
    "f_debt_to_equity", "f_debt_to_assets",
    "f_current_ratio", "f_quick_ratio",
    "f_asset_turnover", "f_roe", "f_roa",
    "f_ocf_to_revenue", "f_fcf_to_revenue", "f_ocf_to_net_income",
    "f_revenue_growth_yoy", "f_profit_growth_yoy",
    "f_revenue_cagr", "f_profit_cagr",
    "f_interest_coverage", "f_eps",
]
