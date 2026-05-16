from datetime import datetime, timezone

import pandas as pd

from tradingagents.agents.analysts.sentiment_analyst import _build_crypto_system_message
from tradingagents.dataflows import alternative_me_data, free_crypto_news_data, okx_data


def test_fear_greed_filters_to_analysis_window(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "data": [
                    {"timestamp": str(int(datetime(2026, 5, 16, tzinfo=timezone.utc).timestamp())), "value": "90", "value_classification": "Extreme Greed"},
                    {"timestamp": str(int(datetime(2026, 5, 15, tzinfo=timezone.utc).timestamp())), "value": "40", "value_classification": "Fear"},
                    {"timestamp": str(int(datetime(2026, 5, 14, tzinfo=timezone.utc).timestamp())), "value": "30", "value_classification": "Fear"},
                ]
            }

    alternative_me_data._CACHE.clear()
    monkeypatch.setattr(alternative_me_data.requests, "get", lambda *args, **kwargs: Response())

    result = alternative_me_data.get_fear_greed_block("2026-05-15", look_back_days=2)

    assert "2026-05-16" not in result
    assert "2026-05-15" in result
    assert "2026-05-14" in result
    assert "Latest as of 2026-05-15: 40" in result


def test_free_crypto_news_filters_to_analysis_window(monkeypatch):
    class Response:
        content = b"""
        <rss><channel>
          <item><title>future Bitcoin headline</title><description>BTC</description><link>https://example.com/future</link><pubDate>Sat, 16 May 2026 00:00:00 GMT</pubDate></item>
          <item><title>in window Bitcoin ETF headline</title><description>BTC</description><link>https://example.com/in-window</link><pubDate>Fri, 15 May 2026 00:00:00 GMT</pubDate></item>
          <item><title>too old Bitcoin headline</title><description>BTC</description><link>https://example.com/old</link><pubDate>Wed, 13 May 2026 00:00:00 GMT</pubDate></item>
          <item><title>irrelevant Solana headline</title><description>SOL</description><link>https://example.com/sol</link><pubDate>Fri, 15 May 2026 00:00:00 GMT</pubDate></item>
        </channel></rss>
        """

        def raise_for_status(self):
            pass

    free_crypto_news_data._CACHE.clear()
    monkeypatch.setattr(free_crypto_news_data.requests, "get", lambda *args, **kwargs: Response())

    result = free_crypto_news_data.get_free_crypto_news("BTC", "2026-05-15", look_back_days=2)

    assert "future" not in result
    assert "too old" not in result
    assert "irrelevant" not in result
    assert "in window Bitcoin ETF headline" in result
    assert "2026-05-14 to 2026-05-15" in result


def test_crypto_sentiment_prompt_has_four_layers():
    result = _build_crypto_system_message(
        ticker="BTC/USDT",
        start_date="2026-05-08",
        end_date="2026-05-15",
        fg_block="fg",
        votes_block="votes",
        smart_money_block="smart",
        margin_leverage_block="margin",
    )

    assert "<fear_greed_index_30d>" in result
    assert "<platform_sentiment_votes>" in result
    assert "<okx_signal_trader_positioning>" in result
    assert "<okx_margin_leverage_usage>" in result
    assert "smart" in result
    assert "margin" in result


def test_okx_liquidations_do_not_infer_usd_notional(monkeypatch):
    def fake_request(path, params):
        assert params["uly"] == "BTC-USDT"
        return [
            {"details": [
                {"side": "sell", "sz": "2", "bkPx": "100000"},
                {"side": "buy", "sz": "3", "bkPx": "100000"},
            ]}
        ]

    monkeypatch.setattr(okx_data, "_okx_request", fake_request)

    result = okx_data.get_okx_liquidation_orders("SWAP", "BTC")

    assert "contracts" in result
    assert "$" not in result
    assert "USD notional is not inferred" in result
    assert "Long liquidations:  2.0000 contracts" in result
    assert "Short liquidations: 3.0000 contracts" in result


def test_okx_mark_price_outputs_spot_basis(monkeypatch):
    def fake_request(path, params):
        if path == "/api/v5/market/mark-price-candles":
            return [["1778803200000", "99", "101", "98", "100", "1"]]
        if path == "/api/v5/market/ticker":
            return [{"last": "98"}]
        raise AssertionError(path)

    monkeypatch.setattr(okx_data, "_okx_request", fake_request)

    result = okx_data.get_okx_mark_price_candles("BTC/USDT", bar="1H")

    assert "Latest spot basis" in result
    assert "mark 100 vs spot 98" in result
    assert "+2.041%" in result


def test_okx_compact_csv_block_summarizes_recent_rows():
    df = pd.DataFrame(
        {
            "timestamp": ["2026-05-14", "2026-05-15"],
            "ratio": [1.0, 1.5],
        }
    )

    result = okx_data._compact_csv_block("title", df, max_rows=1)

    assert "title: 2 rows from 2026-05-14 to 2026-05-15" in result
    assert "ratio: latest=1.5, change=+0.5" in result
    assert "2026-05-15,1.5" in result
    assert "2026-05-14,1.0" not in result
