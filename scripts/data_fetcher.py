# data_fetcher.py
import requests
import pandas as pd
from datetime import datetime
import logging
from typing import Tuple, Optional, Dict, Any
from requests.exceptions import RequestException
from functools import lru_cache
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Custom exception for API-related errors."""
    pass


@lru_cache(maxsize=100)
def fetch_stock_data(symbol: str, start_date: str, end_date: str) -> Tuple[Optional[pd.DataFrame], Dict[str, Any]]:
    """
    Fetch stock data with caching and proper error handling.
    """
    API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')
    if not API_KEY:
        raise APIError("API key not configured. Please set ALPHA_VANTAGE_API_KEY in .env file")

    BASE_URL = 'https://www.alphavantage.co/query'

    try:
        # Fetch historical data
        historical_data = fetch_historical_data(BASE_URL, symbol, API_KEY)
        if historical_data is not None:
            historical_data = process_historical_data(historical_data, start_date, end_date)

        # Fetch real-time data
        real_time_data = fetch_real_time_data(BASE_URL, symbol, API_KEY)

        return historical_data, real_time_data

    except RequestException as e:
        logger.error(f"Network error while fetching data: {str(e)}")
        raise APIError(f"Failed to fetch data: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing data: {str(e)}", exc_info=True)
        raise APIError(f"Error processing data: {str(e)}")


def fetch_historical_data(base_url: str, symbol: str, api_key: str) -> Optional[pd.DataFrame]:
    """Fetch historical data from API."""
    params = {
        'function': 'TIME_SERIES_DAILY',
        'symbol': symbol,
        'apikey': api_key,
        'outputsize': 'full'
    }

    response = requests.get(base_url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    if 'Time Series (Daily)' not in data:
        logger.error(f"API Error: {data.get('Error Message', 'Unknown error')}")
        return None

    return pd.DataFrame(data['Time Series (Daily)']).T


def fetch_real_time_data(base_url: str, symbol: str, api_key: str) -> Dict[str, Any]:
    """Fetch real-time data from API."""
    params = {
        'function': 'GLOBAL_QUOTE',
        'symbol': symbol,
        'apikey': api_key
    }

    response = requests.get(base_url, params=params, timeout=10)
    response.raise_for_status()
    quote_data = response.json().get('Global Quote', {})

    return {
        'current_price': safe_float(quote_data.get('05. price')),
        'change': safe_float(quote_data.get('09. change')),
        'change_percent': safe_float(quote_data.get('10. change percent', '0%').strip('%')),
        'volume': safe_int(quote_data.get('06. volume')),
        'market_cap': quote_data.get('06. market cap'),
        'pe_ratio': None,
        '52wk_high': None,
        '52wk_low': None
    }


def process_historical_data(data: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    """Process and clean historical data."""
    data.index = pd.to_datetime(data.index)
    data = data.sort_index()
    data = data.loc[start_date:end_date]

    data.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

    # Convert columns to appropriate types
    numeric_columns = ['Open', 'High', 'Low', 'Close']
    for col in numeric_columns:
        data[col] = pd.to_numeric(data[col], errors='coerce')

    data['Volume'] = pd.to_numeric(data['Volume'], errors='coerce').fillna(0).astype(int)

    return data


def safe_float(value: Any) -> Optional[float]:
    """Safely convert value to float."""
    try:
        return float(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def safe_int(value: Any) -> Optional[int]:
    """Safely convert value to integer."""
    try:
        return int(value) if value is not None else None
    except (ValueError, TypeError):
        return None