import os
import pytest
from tradingagents.llm_clients.headers_env import load_custom_headers


def test_unset_returns_none():
    os.environ.pop("CUSTOM_TEST_HEADERS", None)
    assert load_custom_headers("CUSTOM_TEST_HEADERS") is None


def test_empty_string_returns_none():
    os.environ["CUSTOM_TEST_HEADERS"] = ""
    assert load_custom_headers("CUSTOM_TEST_HEADERS") is None
    del os.environ["CUSTOM_TEST_HEADERS"]


def test_valid_json_object():
    os.environ["CUSTOM_TEST_HEADERS"] = '{"User-Agent": "my-bot/1.0", "X-Custom": "foo"}'
    result = load_custom_headers("CUSTOM_TEST_HEADERS")
    assert result == {"User-Agent": "my-bot/1.0", "X-Custom": "foo"}
    del os.environ["CUSTOM_TEST_HEADERS"]


def test_malformed_json_raises_valueerror():
    os.environ["CUSTOM_TEST_HEADERS"] = "not-json"
    with pytest.raises(ValueError, match="CUSTOM_TEST_HEADERS"):
        load_custom_headers("CUSTOM_TEST_HEADERS")
    del os.environ["CUSTOM_TEST_HEADERS"]


def test_non_dict_raises_valueerror():
    os.environ["CUSTOM_TEST_HEADERS"] = '["list", "not", "dict"]'
    with pytest.raises(ValueError, match="CUSTOM_TEST_HEADERS"):
        load_custom_headers("CUSTOM_TEST_HEADERS")
    del os.environ["CUSTOM_TEST_HEADERS"]
