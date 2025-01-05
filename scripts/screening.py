import yfinance as yf
import pandas as pd
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def fetch_stock_data(stock_symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """
    Fetch stock data using yfinance with error handling.
    """
    try:
        stock_data = yf.download(stock_symbol, start=start_date, end=end_date, progress=False)
        if stock_data.empty:
            logger.warning(f"No data found for symbol {stock_symbol}")
            return None
        return stock_data
    except Exception as e:
        logger.error(f"Error fetching data for {stock_symbol}: {str(e)}", exc_info=True)
        return None


def get_stock_table_html(stock_symbol: str, start_date: str, end_date: str) -> Optional[str]:
    """
    Generate HTML table from stock data with error handling.
    """
    try:
        stock_data = fetch_stock_data(stock_symbol, start_date, end_date)
        if stock_data is None:
            return None

        stock_data = process_stock_data(stock_data)

        return stock_data.to_html(
            classes='table table-striped',
            header=True,
            index=False,
            float_format=lambda x: '%.2f' % x
        )
    except Exception as e:
        logger.error(f"Error generating table for {stock_symbol}: {str(e)}", exc_info=True)
        return None


def process_stock_data(data: pd.DataFrame) -> pd.DataFrame:
    """Process and clean stock data."""
    data = data.copy()
    data.reset_index(inplace=True)

    if 'Date' not in data.columns:
        data.rename(columns={'index': 'Date'}, inplace=True)

    data['Date'] = pd.to_datetime(data['Date']).dt.strftime('%Y-%m-%d')

    # Round numeric columns to 2 decimal places
    numeric_columns = ['Open', 'High', 'Low', 'Close', 'Adj Close']
    data[numeric_columns] = data[numeric_columns].round(2)

    return data