"""
Screener.in Data Loader Module
Handles reading and parsing Screener.in Excel export format
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple
from datetime import datetime
import json
import os


class ScreenerDataLoader:
    """Loads and parses financial data from Screener.in Excel exports"""

    def __init__(self, filepath: str, mapping_path: Optional[str] = None):
        self.filepath = filepath
        self.mapping_path = mapping_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'screener_mapping.json'
        )
        self.mapping = self._load_mapping()

        self.company_info = {}
        self.income_statement = None
        self.balance_sheet = None
        self.cash_flow = None
        self.quarters_data = None
        self.peers_data = None
        self.years = []
        self.raw_sheets = {}

    def _load_mapping(self) -> Dict:
        """Load the mapping configuration"""
        try:
            with open(self.mapping_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load mapping file: {e}")
            return {}

    def load_all_data(self) -> Dict:
        """Load all sheets from the Excel file"""
        try:
            # Load all sheets
            xl = pd.ExcelFile(self.filepath)
            for sheet in xl.sheet_names:
                self.raw_sheets[sheet] = pd.read_excel(xl, sheet_name=sheet, header=None)

            # Load Company Info from Data Sheet
            self.company_info = self._load_company_info()

            # Load Financial Statements
            self.income_statement = self._load_profit_loss()
            self.balance_sheet = self._load_balance_sheet()
            self.cash_flow = self._load_cash_flow()
            self.quarters_data = self._load_quarters()

            # Extract years
            self._extract_years()

            return {
                "company_info": self.company_info,
                "income_statement": self.income_statement,
                "balance_sheet": self.balance_sheet,
                "cash_flow": self.cash_flow,
                "quarters_data": self.quarters_data,
                "peers_data": self.peers_data,
                "years": self.years
            }
        except Exception as e:
            raise Exception(f"Error loading data: {str(e)}")

    def _load_company_info(self) -> Dict:
        """Load company information from Data Sheet"""
        info = {}
        try:
            if 'Data Sheet' in self.raw_sheets:
                df = self.raw_sheets['Data Sheet']

                # Company name from row 0, col 1
                info['company_name'] = str(df.iloc[0, 1]).strip() if pd.notna(df.iloc[0, 1]) else 'Unknown Company'

                # Parse META section
                for i in range(df.shape[0]):
                    label = str(df.iloc[i, 0]).strip() if pd.notna(df.iloc[i, 0]) else ''
                    value = df.iloc[i, 1] if df.shape[1] > 1 else None

                    if 'Number of shares' in label:
                        info['shares_outstanding'] = float(value) * 1e7 if pd.notna(value) else 0  # Convert to actual number (in Cr)
                    elif 'Face Value' in label:
                        info['face_value'] = float(value) if pd.notna(value) else 1
                    elif 'Current Price' in label:
                        info['current_stock_price'] = float(value) if pd.notna(value) else 0
                    elif 'Market Capitalization' in label:
                        info['market_cap'] = float(value) if pd.notna(value) else 0

                # Set defaults
                info['ticker_symbol'] = info['company_name'].split()[0] if info['company_name'] else ''
                info['industry'] = 'Default'  # User can change this
                info['analysis_date'] = datetime.now().strftime("%Y-%m-%d")

        except Exception as e:
            print(f"Warning: Error loading company info: {e}")
            info = {
                'company_name': 'Unknown Company',
                'ticker_symbol': '',
                'industry': 'Default',
                'current_stock_price': 0,
                'shares_outstanding': 0,
                'analysis_date': datetime.now().strftime("%Y-%m-%d")
            }

        return info

    def _parse_sheet_with_header(self, sheet_name: str, skip_trailing: bool = True) -> Tuple[pd.DataFrame, List[str]]:
        """Parse a sheet with Screener.in format (header in row 1)"""
        if sheet_name not in self.raw_sheets:
            return None, []

        df = self.raw_sheets[sheet_name].copy()

        # Find header row (contains 'Narration')
        header_row = None
        for i in range(min(5, len(df))):
            if pd.notna(df.iloc[i, 0]) and 'Narration' in str(df.iloc[i, 0]):
                header_row = i
                break

        if header_row is None:
            header_row = 1  # Default to row 1

        # Extract column headers (dates)
        headers = df.iloc[header_row].tolist()

        # Convert date headers to strings
        periods = []
        for h in headers[1:]:  # Skip 'Narration' column
            if pd.notna(h):
                if isinstance(h, datetime):
                    # Format as Mar-YY
                    periods.append(h.strftime('Mar-%y'))
                elif isinstance(h, str):
                    if h not in ['Trailing', 'Best Case', 'Worst Case', 'SCREENER.IN']:
                        periods.append(h)
                    elif h == 'Trailing' and not skip_trailing:
                        periods.append(h)

        # Extract data rows
        data_rows = []
        for i in range(header_row + 1, len(df)):
            row_data = df.iloc[i].tolist()
            metric_name = row_data[0]

            if pd.isna(metric_name) or str(metric_name).strip() == '':
                continue
            if str(metric_name).strip() in ['RATIOS:', 'NaN', 'TRENDS:']:
                continue

            data_rows.append(row_data)

        # Create DataFrame with proper structure
        if data_rows:
            result_df = pd.DataFrame(data_rows)
            result_df.columns = headers[:len(result_df.columns)]
            result_df = result_df.rename(columns={result_df.columns[0]: 'Metric'})
            result_df = result_df.set_index('Metric')

            # Rename date columns to consistent format
            new_cols = {}
            col_idx = 0
            for col in result_df.columns:
                if isinstance(col, datetime):
                    new_cols[col] = col.strftime('Mar-%y')
                elif col in ['Trailing', 'Best Case', 'Worst Case', 'SCREENER.IN']:
                    if col == 'Trailing' and not skip_trailing:
                        new_cols[col] = 'TTM'
                    else:
                        continue

            result_df = result_df.rename(columns=new_cols)

            # Keep only year columns (Mar-XX format)
            valid_cols = [c for c in result_df.columns if isinstance(c, str) and
                         (c.startswith('Mar-') or c.startswith('FY') or c == 'TTM')]
            if valid_cols:
                result_df = result_df[valid_cols]

            # Convert to numeric
            result_df = result_df.apply(pd.to_numeric, errors='coerce')

            return result_df, valid_cols

        return None, []

    def _load_profit_loss(self) -> pd.DataFrame:
        """Load Profit & Loss statement"""
        df, periods = self._parse_sheet_with_header('Profit & Loss')
        if df is None:
            return None

        # Map to standard income statement format (matching FinancialAnalyzer expectations)
        metric_mapping = {
            'Sales': 'Revenue',
            'Expenses': 'Cost of Goods Sold',  # Total Expenses maps to COGS for analysis
            'Operating Profit': 'EBIT',  # Operating Profit = EBIT
            'Other Income': 'Other Income',
            'Depreciation': 'Depreciation',
            'Interest': 'Interest Expense',
            'Profit before tax': 'Profit Before Tax',
            'Tax': 'Tax Expense',
            'Net profit': 'Net Profit',
            'EPS': 'EPS',
            'OPM': 'Operating Margin',
            'Dividend Payout': 'Dividend Payout Ratio'
        }

        # Create standardized income statement
        income_data = {}
        for old_name, new_name in metric_mapping.items():
            if old_name in df.index:
                income_data[new_name] = df.loc[old_name]

        # Calculate derived metrics
        if 'Revenue' in income_data:
            # EBITDA = EBIT + Depreciation
            if 'EBIT' in income_data and 'Depreciation' in income_data:
                income_data['EBITDA'] = income_data['EBIT'] + income_data['Depreciation']

            # Gross Profit approximation (Revenue - Direct Costs)
            if 'Cost of Goods Sold' in income_data and 'Depreciation' in income_data and 'Interest Expense' in income_data:
                # Gross Profit = Revenue - (COGS - Depreciation - Interest) since COGS includes all expenses
                direct_costs = income_data['Cost of Goods Sold'] - income_data['Depreciation'] - income_data['Interest Expense']
                income_data['Gross Profit'] = income_data['Revenue'] - direct_costs

            # Operating Profit (same as EBIT)
            if 'EBIT' in income_data:
                income_data['Operating Profit'] = income_data['EBIT']

        result_df = pd.DataFrame(income_data).T
        result_df.index.name = 'Metric'
        return result_df

    def _load_balance_sheet(self) -> pd.DataFrame:
        """Load Balance Sheet"""
        df, periods = self._parse_sheet_with_header('Balance Sheet')
        if df is None:
            return None

        # Map to standard balance sheet format
        balance_data = {}

        # Direct mappings (matching FinancialAnalyzer expectations)
        direct_mappings = {
            'Equity Share Capital': 'Share Capital',
            'Reserves': 'Reserves',
            'Borrowings': 'Borrowings',  # Keep as Borrowings for debt calculations
            'Other Liabilities': 'Other Liabilities',
            'Net Block': 'Fixed Assets',
            'Capital Work in Progress': 'Capital Work in Progress',
            'Investments': 'Investments',
            'Other Assets': 'Other Assets',
            'Working Capital': 'Working Capital',
            'Debtors': 'Receivables',
            'Inventory': 'Inventory',
            'Debtor Days': 'Debtor Days',
            'Inventory Turnover': 'Inventory Turnover'
        }

        for old_name, new_name in direct_mappings.items():
            if old_name in df.index:
                balance_data[new_name] = df.loc[old_name]

        # Total appears twice - need to handle carefully
        # First occurrence is Total Liabilities + Equity, Second is Total Assets
        if 'Total' in df.index:
            total_rows = df.loc['Total']
            if isinstance(total_rows, pd.DataFrame):
                balance_data['Total Assets'] = total_rows.iloc[0]
            else:
                balance_data['Total Assets'] = total_rows

        # Calculate derived metrics
        if 'Share Capital' in balance_data and 'Reserves' in balance_data:
            balance_data['Total Equity'] = balance_data['Share Capital'] + balance_data['Reserves']

        if 'Borrowings' in balance_data and 'Other Liabilities' in balance_data:
            balance_data['Total Liabilities'] = balance_data['Borrowings'] + balance_data['Other Liabilities']

        # Current Assets estimation
        if all(k in balance_data for k in ['Receivables', 'Inventory']):
            # Try to get Cash & Bank from Data Sheet or estimate
            current_assets = balance_data['Receivables'] + balance_data['Inventory']
            if 'Other Assets' in balance_data:
                # Other Assets includes some current assets
                current_assets = current_assets + (balance_data['Other Assets'] * 0.5)  # Rough estimate
            balance_data['Current Assets'] = current_assets

        # Current Liabilities estimation (Other Liabilities is a rough proxy)
        if 'Other Liabilities' in balance_data:
            balance_data['Current Liabilities'] = balance_data['Other Liabilities']

        # Short-term and Long-term debt split (estimate 30% short-term)
        if 'Borrowings' in balance_data:
            balance_data['Short-term Debt'] = balance_data['Borrowings'] * 0.3
            balance_data['Long-term Debt'] = balance_data['Borrowings'] * 0.7

        # Payables estimation
        if 'Other Liabilities' in balance_data:
            balance_data['Payables'] = balance_data['Other Liabilities'] * 0.5

        # Cash & Equivalents - try to get from Data Sheet
        if 'Data Sheet' in self.raw_sheets:
            data_df = self.raw_sheets['Data Sheet']
            for i in range(data_df.shape[0]):
                if pd.notna(data_df.iloc[i, 0]) and 'Cash & Bank' in str(data_df.iloc[i, 0]):
                    cash_row = data_df.iloc[i, 1:].tolist()
                    # Create series with same index as other metrics
                    if 'Receivables' in balance_data:
                        cash_values = []
                        for j, col in enumerate(balance_data['Receivables'].index):
                            if j < len(cash_row) and pd.notna(cash_row[j]):
                                cash_values.append(float(cash_row[j]))
                            else:
                                cash_values.append(np.nan)
                        balance_data['Cash & Equivalents'] = pd.Series(cash_values, index=balance_data['Receivables'].index)
                    break

        result_df = pd.DataFrame(balance_data).T
        result_df.index.name = 'Metric'
        return result_df

    def _load_cash_flow(self) -> pd.DataFrame:
        """Load Cash Flow statement"""
        df, periods = self._parse_sheet_with_header('Cash Flow')
        if df is None:
            return None

        # Map to standard cash flow format
        cf_mapping = {
            'Cash from Operating Activity': 'Operating Cash Flow',
            'Cash from Investing Activity': 'Investing Cash Flow',
            'Cash from Financing Activity': 'Financing Cash Flow',
            'Net Cash Flow': 'Net Cash Flow'
        }

        cf_data = {}
        for old_name, new_name in cf_mapping.items():
            if old_name in df.index:
                cf_data[new_name] = df.loc[old_name]

        # Calculate derived metrics
        if 'Operating Cash Flow' in cf_data and 'Investing Cash Flow' in cf_data:
            cf_data['Free Cash Flow'] = cf_data['Operating Cash Flow'] + cf_data['Investing Cash Flow']

        if 'Investing Cash Flow' in cf_data:
            cf_data['Capital Expenditure'] = -cf_data['Investing Cash Flow']  # CapEx is typically negative

        # Dividends Paid - try to extract from financing or estimate from P&L
        if 'Financing Cash Flow' in cf_data:
            # Rough estimate - typically dividends are part of financing outflow
            cf_data['Dividends Paid'] = cf_data['Financing Cash Flow'].apply(
                lambda x: min(0, x) * 0.3 if pd.notna(x) else np.nan
            )

        result_df = pd.DataFrame(cf_data).T
        result_df.index.name = 'Metric'
        return result_df

    def _load_quarters(self) -> pd.DataFrame:
        """Load quarterly data"""
        df, periods = self._parse_sheet_with_header('Quarters')
        return df

    def _extract_years(self):
        """Extract years from the data"""
        if self.income_statement is not None:
            self.years = list(self.income_statement.columns)
        elif self.balance_sheet is not None:
            self.years = list(self.balance_sheet.columns)

    def get_metric(self, statement: str, metric_name: str, year: Optional[str] = None) -> float:
        """Get a specific metric from the financial statements"""
        df = None
        if statement == "income":
            df = self.income_statement
        elif statement == "balance":
            df = self.balance_sheet
        elif statement == "cashflow":
            df = self.cash_flow
        elif statement == "quarters":
            df = self.quarters_data

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
                if df.shape[0] > 0 and 'SCREENER' in str(df.iloc[0]).upper():
                    return 'screener'
            return 'unknown'
    except:
        return 'unknown'
