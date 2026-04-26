import unittest

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.llm_clients.anthropic_client import AnthropicClient
from tradingagents.llm_clients.factory import create_llm_client
from tradingagents.llm_clients.model_catalog import get_model_options
from tradingagents.llm_clients.openai_client import OpenAIClient
from tradingagents.llm_clients.validators import validate_model


class CustomLLMProviderTests(unittest.TestCase):
    def test_custom_openai_uses_openai_client(self):
        client = create_llm_client(
            "custom_openai",
            "custom-openai-model",
            base_url="https://example.com/v1",
            api_key="test-key",
        )

        self.assertIsInstance(client, OpenAIClient)
        self.assertEqual(client.provider, "custom_openai")
        self.assertEqual(client.base_url, "https://example.com/v1")
        self.assertEqual(client.kwargs["api_key"], "test-key")

    def test_custom_anthropic_uses_anthropic_client(self):
        client = create_llm_client(
            "custom_anthropic",
            "custom-anthropic-model",
            base_url="https://example.com/anthropic",
            api_key="test-key",
        )

        self.assertIsInstance(client, AnthropicClient)
        self.assertEqual(client.provider, "custom_anthropic")
        self.assertEqual(client.base_url, "https://example.com/anthropic")
        self.assertEqual(client.kwargs["api_key"], "test-key")

    def test_graph_provider_kwargs_include_llm_api_key(self):
        graph = object.__new__(TradingAgentsGraph)
        graph.config = {
            "llm_provider": "custom_openai",
            "llm_api_key": "test-key",
        }

        self.assertEqual(graph._get_provider_kwargs()["api_key"], "test-key")

    def test_custom_provider_model_options_include_custom_entry(self):
        for provider in ("custom_openai", "custom_anthropic"):
            for mode in ("quick", "deep"):
                with self.subTest(provider=provider, mode=mode):
                    options = get_model_options(provider, mode)
                    self.assertIn(("Custom model ID", "custom"), options)

    def test_custom_providers_accept_arbitrary_model_names(self):
        for provider in ("custom_openai", "custom_anthropic"):
            with self.subTest(provider=provider):
                self.assertTrue(validate_model(provider, "provider-specific-model-name"))


if __name__ == "__main__":
    unittest.main()
