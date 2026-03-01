"""
Data Loader Module
Handles reading and parsing Excel files with company financials
Supports both standard format and Screener.in export format
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from datetime import datetime


def detect_file_format(filepath: str) -> str:
    """Detect whether file is Screener.in format or standard format"""
    try:
        xl = pd.ExcelFile(filepath)
        sheets = xl.sheet_names

        # Check for Screener.in format indicators
        if 'Data Sheet' in sheets and 'Profit & Loss' in sheets:
            return 'screener'
        elif 'Company Info' in sheets and 'Income Statement' in sheets:
            return 'standard'
        else:
            # Try to detect from content
            if 'Profit & Loss' in sheets:
                df = pd.read_excel(xl, sheet_name='Profit & Loss', header=None)
                if df.shape[0] > 0:
                    first_cell = str(df.iloc[0, 0]) if pd.notna(df.iloc[0, 0]) else ''
                    if 'SCREENER' in first_cell.upper() or any('SCREENER' in str(c).upper() for c in df.columns):
                        return 'screener'
            return 'unknown'
    except:
        return 'unknown'


class DataLoader:
    """
    Unified data loader that auto-detects file format and loads appropriately.
    Supports both standard format and Screener.in export format.
    """

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.format = detect_file_format(filepath)
        self.company_info = {}
        self.income_statement = None
        self.balance_sheet = None
        self.cash_flow = None
        self.quarters_data = None
        self.peers_data = None
        self.years = []
        self._loader = None

    def load_all_data(self) -> Dict:
        """Load all sheets from the Excel file based on detected format"""
        if self.format == 'screener':
            return self._load_screener_format()
        else:
            return self._load_standard_format()

    def _load_screener_format(self) -> Dict:
        """Load data from Screener.in Excel export format"""
        try:
            from .screener_data_loader import ScreenerDataLoader
            self._loader = ScreenerDataLoader(self.filepath)
            data = self._loader.load_all_data()

            self.company_info = data['company_info']
            self.income_statement = data['income_statement']
            self.balance_sheet = data['balance_sheet']
            self.cash_flow = data['cash_flow']
            self.quarters_data = data.get('quarters_data')
            self.peers_data = data.get('peers_data')
            self.years = data['years']

            return data
        except Exception as e:
            raise Exception(f"Error loading Screener format: {str(e)}")

    def _load_standard_format(self) -> Dict:
        """Load data from standard Excel format"""
        try:
            # Load Company Info
            self.company_info = self._load_company_info()

            # Load Financial Statements
            self.income_statement = self._load_income_statement()
            self.balance_sheet = self._load_balance_sheet()
            self.cash_flow = self._load_cash_flow()

            # Load Peers if available
            self.peers_data = self._load_peers()

            # Extract years
            self._extract_years()

            return {
                "company_info": self.company_info,
                "income_statement": self.income_statement,
                "balance_sheet": self.balance_sheet,
                "cash_flow": self.cash_flow,
                "peers_data": self.peers_data,
                "years": self.years
            }
        except Exception as e:
            raise Exception(f"Error loading data: {str(e)}")

    def _load_company_info(self) -> Dict:
        """Load company information sheet"""
        try:
            df = pd.read_excel(self.filepath, sheet_name="Company Info", header=None)
            info = {}
            for _, row in df.iterrows():
                if pd.notna(row[0]) and pd.notna(row[1]):
                    key = str(row[0]).strip().lower().replace(" ", "_")
                    info[key] = row[1]
            return info
        except Exception as e:
            return {"error": str(e)}

    def _load_income_statement(self) -> pd.DataFrame:
        """Load income statement data"""
        try:
            df = pd.read_excel(self.filepath, sheet_name="Income Statement", index_col=0)
            df = df.apply(pd.to_numeric, errors='coerce')
            df.index = df.index.str.strip()
            return df
        except Exception as e:
            print(f"Warning: Could not load Income Statement: {e}")
            return None

    def _load_balance_sheet(self) -> pd.DataFrame:
        """Load balance sheet data"""
        try:
            df = pd.read_excel(self.filepath, sheet_name="Balance Sheet", index_col=0)
            df = df.apply(pd.to_numeric, errors='coerce')
            df.index = df.index.str.strip()
            return df
        except Exception as e:
            print(f"Warning: Could not load Balance Sheet: {e}")
            return None

    def _load_cash_flow(self) -> pd.DataFrame:
        """Load cash flow statement data"""
        try:
            df = pd.read_excel(self.filepath, sheet_name="Cash Flow", index_col=0)
            df = df.apply(pd.to_numeric, errors='coerce')
            df.index = df.index.str.strip()
            return df
        except Exception as e:
            print(f"Warning: Could not load Cash Flow: {e}")
            return None

    def _load_peers(self) -> pd.DataFrame:
        """Load peer comparison data if available"""
        try:
            df = pd.read_excel(self.filepath, sheet_name="Peers", index_col=0)
            return df
        except:
            return None

    def _extract_years(self):
        """Extract years from the data"""
        if self.income_statement is not None:
            self.years = list(self.income_statement.columns)
        elif self.balance_sheet is not None:
            self.years = list(self.balance_sheet.columns)

    def get_metric(self, statement: str, metric_name: str, year: Optional[str] = None) -> float:
        """Get a specific metric from the financial statements"""
        # If using screener loader, delegate to it
        if self._loader is not None:
            return self._loader.get_metric(statement, metric_name, year)

        df = None
        if statement == "income":
            df = self.income_statement
        elif statement == "balance":
            df = self.balance_sheet
        elif statement == "cashflow":
            df = self.cash_flow

        if df is None:
            return np.nan

        # Try exact match first
        if metric_name in df.index:
            if year:
                return df.loc[metric_name, year] if year in df.columns else np.nan
            return df.loc[metric_name]

        # Try case-insensitive partial match
        for idx in df.index:
            if metric_name.lower() in str(idx).lower():
                if year:
                    return df.loc[idx, year] if year in df.columns else np.nan
                return df.loc[idx]

        return np.nan

    def get_latest_year(self) -> str:
        """Get the most recent year in the data"""
        if self.years:
            return self.years[-1]
        return None

    def get_all_years_data(self, statement: str, metric_name: str) -> pd.Series:
        """Get metric values for all years"""
        result = self.get_metric(statement, metric_name)
        if isinstance(result, pd.Series):
            return result
        return pd.Series()


def safe_divide(numerator, denominator, default=np.nan):
    """Safely divide two numbers, handling zeros and NaN"""
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return default
    return numerator / denominator


def calculate_growth_rate(values: pd.Series) -> float:
    """Calculate compound annual growth rate"""
    values = values.dropna()
    if len(values) < 2:
        return np.nan
    
    first_val = values.iloc[0]
    last_val = values.iloc[-1]
    periods = len(values) - 1
    
    if first_val <= 0 or last_val <= 0:
        return np.nan
    
    return ((last_val / first_val) ** (1 / periods) - 1) * 100


def calculate_yoy_growth(values: pd.Series) -> pd.Series:
    """Calculate year-over-year growth rates"""
    return values.pct_change() * 100
