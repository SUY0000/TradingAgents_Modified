from unittest.mock import Mock, patch

import pytest

from tradingagents.llm_clients.custom_model_discovery import FetchError, fetch_custom_models


def _response(body, ok=True, status_code=200, text=""):
    response = Mock()
    response.ok = ok
    response.status_code = status_code
    response.text = text
    response.json.return_value = body
    return response


@patch("tradingagents.llm_clients.custom_model_discovery.requests.get")
def test_fetch_custom_models_accepts_data_list(mock_get):
    mock_get.return_value = _response({"data": [{"id": "b"}, {"id": "a"}]})

    assert fetch_custom_models("custom_openai", "https://example.com/v1", "sk") == ["a", "b"]


@patch("tradingagents.llm_clients.custom_model_discovery.requests.get")
def test_fetch_custom_models_accepts_top_level_list(mock_get):
    mock_get.return_value = _response([{"id": "b"}, {"id": "a"}])

    assert fetch_custom_models("custom_openai", "https://example.com/v1", "sk") == ["a", "b"]


@patch("tradingagents.llm_clients.custom_model_discovery.requests.get")
def test_fetch_custom_models_accepts_empty_data_list(mock_get):
    mock_get.return_value = _response({"data": []})

    assert fetch_custom_models("custom_openai", "https://example.com/v1", "sk") == []


@patch("tradingagents.llm_clients.custom_model_discovery.requests.get")
def test_fetch_custom_models_rejects_unexpected_shape(mock_get):
    mock_get.return_value = _response({"unexpected": []})

    with pytest.raises(FetchError, match="Unexpected response shape"):
        fetch_custom_models("custom_openai", "https://example.com/v1", "sk")
