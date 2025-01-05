# app.py
from flask import Flask, render_template, request, jsonify
from scripts.screening import get_stock_table_html
from scripts.data_fetcher import fetch_stock_data
import pandas as pd
from datetime import datetime
from werkzeug.utils import escape
import logging
from typing import Tuple, Optional, Dict, Any
from http import HTTPStatus
from markupsafe import escape

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_url_path='/static')


def validate_dates(start_date: str, end_date: str) -> Tuple[bool, Optional[str]]:
    """Validate date inputs."""
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        if end < start:
            return False, "End date must be after start date"
        if end > datetime.now():
            return False, "End date cannot be in the future"
        return True, None
    except ValueError:
        return False, "Invalid date format. Please use YYYY-MM-DD"


def format_real_time_data(data: Dict[str, Any]) -> Dict[str, str]:
    """Format real-time data with proper error handling."""
    formatters = {
        'current_price': lambda x: f"${x:.2f}" if x else 'N/A',
        'change': lambda x: f"{x:.2f}" if x else 'N/A',
        'change_percent': lambda x: f"{x:.2f}%" if x else 'N/A',
        'volume': lambda x: f"{x:,}" if x else 'N/A',
        'market_cap': lambda x: f"${x:,}" if x else 'N/A',
        'pe_ratio': lambda x: f"{x:.2f}" if x else 'N/A',
        '52wk_high': lambda x: f"${x:.2f}" if x else 'N/A',
        '52wk_low': lambda x: f"${x:.2f}" if x else 'N/A'
    }

    return {key: formatters[key](data.get(key)) for key in formatters}


def format_number(value: float) -> str:
    """Format large numbers with comma separators."""
    try:
        return f"{value:,.0f}" if value is not None else 'N/A'
    except (ValueError, TypeError):
        return 'N/A'


def format_price(value: float) -> str:
    """Format price with dollar sign and two decimal places."""
    try:
        return f"${value:.2f}" if value is not None else 'N/A'
    except (ValueError, TypeError):
        return 'N/A'


def format_percentage(value: float) -> str:
    """Format percentage with two decimal places."""
    try:
        return f"{value:.2f}%" if value is not None else 'N/A'
    except (ValueError, TypeError):
        return 'N/A'


def format_market_cap(value: float) -> str:
    """Format market cap into readable format with B/M suffix."""
    try:
        if value is None:
            return 'N/A'

        if value >= 1e12:  # Trillion
            return f"${value / 1e12:.2f}T"
        elif value >= 1e9:  # Billion
            return f"${value / 1e9:.2f}B"
        elif value >= 1e6:  # Million
            return f"${value / 1e6:.2f}M"
        else:
            return f"${value:,.0f}"
    except (ValueError, TypeError):
        return 'N/A'


def format_real_time_data(data: Dict[str, Any]) -> Dict[str, str]:
    """Format real-time data with proper error handling."""
    formatters = {
        'current_price': lambda x: format_price(x),
        'change': lambda x: format_price(x),
        'change_percent': lambda x: format_percentage(x),
        'volume': lambda x: format_number(x),
        'market_cap': lambda x: format_market_cap(x),
        'pe_ratio': lambda x: f"{x:.2f}" if x else 'N/A',
        '52wk_high': lambda x: format_price(x),
        '52wk_low': lambda x: format_price(x)
    }

    return {key: formatters[key](data.get(key)) for key in formatters}

@app.errorhandler(Exception)
def handle_error(error):
    """Global error handler."""
    logger.error(f"An error occurred: {str(error)}", exc_info=True)
    return render_template('index.html',
                           error="An unexpected error occurred. Please try again later.")


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.ico')

@app.route('/results', methods=['GET', 'POST'])
def results():
    if request.method != 'POST':
        return render_template('index.html')

    try:
        # Get and validate inputs
        stock_symbol = escape(request.form.get('stock_symbol', '').upper().strip())
        start_date = request.form.get('start_date', '2023-01-01')
        end_date = request.form.get('end_date', '2023-12-31')

        if not stock_symbol:
            return render_template('index.html', error="Please enter a stock symbol"), HTTPStatus.BAD_REQUEST

        # Validate dates
        dates_valid, error_message = validate_dates(start_date, end_date)
        if not dates_valid:
            return render_template('index.html', error=error_message), HTTPStatus.BAD_REQUEST

        # Fetch data
        historical_data, real_time_data = fetch_stock_data(stock_symbol, start_date, end_date)

        if historical_data is None or historical_data.empty:
            return render_template('index.html',
                                   error=f"No data found for symbol {stock_symbol}"), HTTPStatus.NOT_FOUND

        # Process historical data
        historical_data = process_historical_data(historical_data)

        # Format real-time data
        formatted_real_time = format_real_time_data(real_time_data)

        return render_template('results.html',
                               symbol=stock_symbol,
                               real_time_data=formatted_real_time,
                               historical_data=historical_data,
                               table_html=historical_data.to_html(
                                   classes='table table-striped table-hover',
                                   header=True,
                                   index=False,
                                   float_format=lambda x: '%.2f' % x
                               ),
                               dates=historical_data['Date'].tolist(),
                               prices=historical_data['Close'].tolist())

    except Exception as e:
        logger.error(f"Error processing request for {stock_symbol}: {str(e)}", exc_info=True)
        return render_template('index.html',
                               error=f"Error processing data for {stock_symbol}"), HTTPStatus.INTERNAL_SERVER_ERROR


def process_historical_data(data: pd.DataFrame) -> pd.DataFrame:
    """Process and clean historical data."""
    data = data.copy()
    if not isinstance(data.index, pd.DatetimeIndex):
        data.index = pd.to_datetime(data.index)

    data.reset_index(inplace=True)
    if 'Date' not in data.columns:
        data.rename(columns={'index': 'Date'}, inplace=True)

    data['Date'] = data['Date'].dt.strftime('%Y-%m-%d')
    return data


if __name__ == "__main__":
    app.run(debug=False)  # Set to False in production
