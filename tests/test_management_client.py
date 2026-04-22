import io
import urllib.error
import unittest
from email.message import Message
from typing import cast

from src.management_client import ManagementClient
from src.retry import ManagementApiError


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def read(self) -> bytes:
        return self.body

    def close(self) -> None:
        return None


class ManagementClientTests(unittest.TestCase):
    def test_management_client_sets_bearer_auth_and_paths(self) -> None:
        captured: dict[str, object] = {}

        def sender(request, timeout):
            captured["url"] = request.full_url
            captured["auth"] = request.headers["Authorization"]
            captured["timeout"] = timeout
            return FakeResponse(b'{"usage": {"apis": {}}}')

        client = ManagementClient(base_url="http://proxy/v0/management", management_key="secret", timeout_seconds=5.0, sender=sender)
        payload = client.export_usage_snapshot()
        self.assertEqual(
            captured,
            {
                "url": "http://proxy/v0/management/usage/export",
                "auth": "Bearer secret",
                "timeout": 5.0,
            },
        )
        self.assertEqual(payload["usage"], {"apis": {}})

    def test_management_client_surfaces_management_errors(self) -> None:
        def sender(request, timeout):
            del timeout
            raise urllib.error.HTTPError(request.full_url, 400, "bad", hdrs=Message(), fp=io.BytesIO(b'{"error":"invalid"}'))

        client = ManagementClient(base_url="http://proxy/v0/management", management_key="secret", timeout_seconds=5.0, sender=sender)
        with self.assertRaises(ManagementApiError) as context:
            client.export_usage_snapshot()
        self.assertEqual(context.exception.status, 400)
        self.assertEqual(str(context.exception), "invalid")

    def test_management_client_import_posts_versioned_usage_payload(self) -> None:
        captured: dict[str, object] = {}

        def sender(request, timeout):
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            captured["body"] = request.data.decode("utf-8") if request.data else ""
            captured["timeout"] = timeout
            return FakeResponse(b'{"added":1,"skipped":0}')

        client = ManagementClient(base_url="http://proxy/v0/management", management_key="secret", timeout_seconds=5.0, sender=sender)
        payload = cast(dict[str, object], {"apis": {"key": {"models": {"gpt-5.4": {"details": []}}}}})
        client.import_usage_snapshot(payload)
        self.assertEqual(captured["url"], "http://proxy/v0/management/usage/import")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["timeout"], 5.0)
        self.assertEqual(captured["body"], '{"version": 1, "usage": {"apis": {"key": {"models": {"gpt-5.4": {"details": []}}}}}}')


if __name__ == "__main__":
    unittest.main()
