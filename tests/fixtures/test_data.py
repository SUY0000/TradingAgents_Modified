"""
Test data for CCXT enhancement tests.

Contains sample data and configurations for testing.
"""

# Test symbols for different exchanges
TEST_SYMBOLS = {
    'okx': 'BTC/USDT',
    'binance': 'ETH/USDT',
    'coinbase': 'BTC-USD',
}

# Timeframes to test
TIMEFRAMES = [
    '1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M'
]

# Sample dates for testing
SAMPLE_START_DATE = '2025-01-01'
SAMPLE_END_DATE = '2025-01-31'
SAMPLE_CURR_DATE = '2025-01-15'

# Sample indicators for testing
INDICATORS = [
    'close_50_sma',
    'close_200_sma',
    'close_10_ema',
    'macd',
    'macds',
    'macdh',
    'rsi',
    'boll',
    'boll_ub',
    'boll_lb',
    'atr',
    'vwma',
    'mfi',
]

# Sample config for testing
TEST_CONFIG = {
    'ccxt_exchange': 'okx',
    'ccxt_symbol': 'BTC/USDT',
    'data_vendors': {
        'core_stock_apis': 'ccxt',
        'technical_indicators': 'ccxt',
    },
    'tool_vendors': {
        'get_stock_data': 'ccxt',
        'get_indicators': 'ccxt',
    },
    'data_cache_dir': '/tmp/test_cache',
}
