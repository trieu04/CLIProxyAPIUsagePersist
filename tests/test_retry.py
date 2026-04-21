import urllib.error
import unittest

from src.cliproxyapi_usage_persist.retry import ManagementApiError, is_transient_failure, retry_call


class RetryTests(unittest.TestCase):
    def test_retry_classifier_marks_expected_errors_transient(self) -> None:
        self.assertTrue(is_transient_failure(ManagementApiError("retry", status=503)))
        self.assertTrue(is_transient_failure(urllib.error.URLError("down")))
        self.assertFalse(is_transient_failure(ManagementApiError("nope", status=400)))

    def test_retry_call_retries_transient_failures_with_backoff(self) -> None:
        calls = {"count": 0}
        sleeps: list[float] = []

        def flaky() -> str:
            calls["count"] += 1
            if calls["count"] < 3:
                raise ManagementApiError("temporary", status=503)
            return "ok"

        result = retry_call(flaky, attempts=4, base_delay_seconds=1.0, max_delay_seconds=8.0, sleep=sleeps.append)
        self.assertEqual(result, "ok")
        self.assertEqual(sleeps, [1.0, 2.0])


if __name__ == "__main__":
    unittest.main()
