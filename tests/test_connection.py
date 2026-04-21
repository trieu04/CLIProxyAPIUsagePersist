import unittest

from src.cliproxyapi_usage_persist.connection import compute_management_url, normalize_api_base


class ConnectionTests(unittest.TestCase):
    def test_normalize_api_base_matches_management_center_behavior(self) -> None:
        self.assertEqual(normalize_api_base(" localhost:8317/v0/management/ "), "http://localhost:8317")
        self.assertEqual(normalize_api_base("https://proxy.example.com///"), "https://proxy.example.com")

    def test_compute_management_url_appends_management_prefix(self) -> None:
        self.assertEqual(compute_management_url("proxy.internal:8317"), "http://proxy.internal:8317/v0/management")


if __name__ == "__main__":
    unittest.main()
