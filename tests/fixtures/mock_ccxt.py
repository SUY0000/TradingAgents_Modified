"""
Mock CCXT exchange for testing.

Provides mock implementations of CCXT exchange methods to avoid
making real API calls during tests.
"""
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock

def create_mock_ccxt_exchange():
    """Create a mock CCXT exchange object.
    
    Returns:
        Mock: A mock CCXT exchange with fetch_ohlcv method.
    """
    mock_exchange = Mock()
    
    # Mock fetch_ohlcv method
    def mock_fetch_ohlcv(symbol, timeframe='1d', since=None, limit=1000):
        # Generate mock candle data
        candles = []
        if since is None:
            # Start from 30 days ago if no since provided
            since = int((datetime.now() - timedelta(days=30)).timestamp() * 1000)
        
        current_time = since
        for i in range(limit):
            # Generate realistic candle data
            open_price = 50000 + i * 10
            high_price = open_price + 100 + (i % 20)
            low_price = open_price - 100 + (i % 15)
            close_price = open_price + 50 - (i % 10)
            volume = 1000 + i * 10
            
            candles.append([
                current_time,  # timestamp
                open_price,    # open
                high_price,    # high  
                low_price,     # low
                close_price,   # close
                volume         # volume
            ])
            
            # Increment by timeframe
            if timeframe == '1d':
                current_time += 86400000  # 1 day in ms
            elif timeframe == '1h':
                current_time += 3600000   # 1 hour in ms
            elif timeframe == '5m':
                current_time += 300000    # 5 minutes in ms
            else:
                # Default to 1 day
                current_time += 86400000
                
            # Stop if we reach "now"
            if current_time > int(datetime.now().timestamp() * 1000):
                break
        
        return candles
    
    mock_exchange.fetch_ohlcv.side_effect = mock_fetch_ohlcv
    mock_exchange.id = 'okx'
    mock_exchange.has = {'fetchOHLCV': True}
    
    return mock_exchange

def create_mock_ohlcv_dataframe(symbol="BTC/USDT", days=30, timeframe='1d'):
    """Create a mock OHLCV DataFrame for testing.
    
    Args:
        symbol: Trading pair symbol
        days: Number of days of data
        timeframe: Timeframe string ('1d', '1h', '5m', etc.)
    
    Returns:
        pd.DataFrame: Mock OHLCV data
    """
    end_date = datetime.now()
    
    # Calculate timeframe increment in days
    if timeframe == '1d':
        freq = 'D'
    elif timeframe == '1h':
        freq = 'H'
    elif timeframe == '5m':
        freq = '5min'
    else:
        freq = 'D'
    
    dates = pd.date_range(end=end_date, periods=days, freq=freq)
    
    data = pd.DataFrame({
        'Date': dates,
        'Open': [50000 + i * 10 for i in range(len(dates))],
        'High': [50100 + i * 10 + (i % 20) for i in range(len(dates))],
        'Low': [49900 + i * 10 - (i % 15) for i in range(len(dates))],
        'Close': [50050 + i * 10 - (i % 10) for i in range(len(dates))],
        'Volume': [1000 + i * 10 for i in range(len(dates))],
        'Adj Close': [50050 + i * 10 - (i % 10) for i in range(len(dates))],
    })
    
    return data
