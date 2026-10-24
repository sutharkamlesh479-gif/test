import unittest

from aurix_agent.config import DEFAULT_CONFIG, enabled_providers, is_allowed_endpoint


class ConfigTests(unittest.TestCase):
    def test_default_config_has_provider(self):
        self.assertEqual(DEFAULT_CONFIG["providers"][0]["name"], "OpenAI-compatible")

    def test_endpoint_policy(self):
        self.assertTrue(is_allowed_endpoint("https://api.example/v1/chat/completions"))
        self.assertTrue(is_allowed_endpoint("http://localhost:11434/v1/chat/completions"))
        self.assertTrue(is_allowed_endpoint("http://127.0.0.1:11434/v1/chat/completions"))
        self.assertFalse(is_allowed_endpoint("http://api.example/v1/chat/completions"))
        self.assertFalse(is_allowed_endpoint("file:///tmp/config.json"))

    def test_enabled_provider_priority(self):
        config = {"active_provider": "B", "providers": [
            {"name": "A", "endpoint": "https://a.example/v1/chat/completions", "model": "a", "enabled": True},
            {"name": "B", "endpoint": "https://b.example/v1/chat/completions", "model": "b", "enabled": True},
            {"name": "Off", "endpoint": "https://off.example/v1/chat/completions", "model": "x", "enabled": False},
        ]}
        result = enabled_providers(config)
        self.assertEqual([p["name"] for p in result], ["B", "A"])


if __name__ == "__main__":
    unittest.main()
