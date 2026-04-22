import unittest

from src.usage_merge import (
    _canonical_timestamp,
    deduped_unique_request_count,
    merge_snapshots,
    normalize_token_stats,
    rebuild_snapshot,
    unique_request_count,
)


def _detail(timestamp: str, *, latency_ms: int = 0, failed: bool = False) -> dict[str, object]:
    return {
        "timestamp": timestamp,
        "latency_ms": latency_ms,
        "source": "user@example.com",
        "auth_index": "0",
        "tokens": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
        "failed": failed,
    }

class UsageMergeTests(unittest.TestCase):
    def test_normalize_token_stats_rebuilds_total_tokens_like_server(self) -> None:
        self.assertEqual(normalize_token_stats({"input_tokens": 1, "output_tokens": 2, "reasoning_tokens": 3})["total_tokens"], 6)

    def test_rebuild_snapshot_recomputes_totals_from_details(self) -> None:
        snapshot = rebuild_snapshot(
            {
                "total_requests": 999,
                "apis": {"key": {"models": {"gpt-5.4": {"details": [_detail("2026-03-20T12:00:00Z", failed=True)]}}}},
            }
        )
        self.assertEqual(snapshot["total_requests"], 1)
        self.assertEqual(snapshot["failure_count"], 1)
        self.assertEqual(snapshot["success_count"], 0)
        self.assertEqual(snapshot["total_tokens"], 30)
        self.assertEqual(snapshot["requests_by_hour"], {"12": 1})

    def test_merge_snapshots_ignores_latency_in_dedup_key(self) -> None:
        first = {"apis": {"key": {"models": {"gpt-5.4": {"details": [_detail("2026-03-20T12:00:00Z", latency_ms=0)]}}}}}
        second = {"apis": {"key": {"models": {"gpt-5.4": {"details": [_detail("2026-03-20T12:00:00Z", latency_ms=2500)]}}}}}
        merged, counts = merge_snapshots(first, second)
        self.assertEqual(unique_request_count(merged), 1)
        self.assertEqual(counts, {"added": 1, "skipped": 1})

    def test_merge_snapshots_accepts_pre_normalized_inputs_without_rebuilding(self) -> None:
        normalized_first = rebuild_snapshot(
            {"apis": {"key": {"models": {"gpt-5.4": {"details": [_detail("2026-03-20T12:00:00Z", latency_ms=0)]}}}}}
        )
        normalized_second = rebuild_snapshot(
            {"apis": {"key": {"models": {"gpt-5.4": {"details": [_detail("2026-03-20T12:00:00Z", latency_ms=2500)]}}}}}
        )

        merged, counts = merge_snapshots(
            normalized_first,
            normalized_second,
            inputs_already_normalized=True,
        )

        self.assertEqual(unique_request_count(merged, snapshot_already_normalized=True), 1)
        self.assertEqual(deduped_unique_request_count(merged, snapshot_already_normalized=True), 1)
        self.assertEqual(counts, {"added": 1, "skipped": 1})

    def test_deduped_unique_request_count_collapses_go_equivalent_duplicates(self) -> None:
        snapshot = {
            "apis": {
                "key": {
                    "models": {
                        "gpt-5.4": {
                            "details": [
                                _detail("2026-03-20T12:00:00Z", latency_ms=0),
                                _detail("2026-03-20T12:00:00Z", latency_ms=2500),
                            ]
                        }
                    }
                }
            }
        }
        self.assertEqual(unique_request_count(snapshot), 2)
        self.assertEqual(deduped_unique_request_count(snapshot), 1)

    def test_canonical_timestamp_matches_go_style_utc_formatting_for_offsets(self) -> None:
        timestamp_text, _ = _canonical_timestamp("2026-03-20T19:00:00+07:00")
        self.assertEqual(timestamp_text, "2026-03-20T12:00:00Z")

    def test_canonical_timestamp_preserves_fractional_precision(self) -> None:
        timestamp_text, _ = _canonical_timestamp("2026-03-20T12:00:00.123456789Z")
        self.assertEqual(timestamp_text, "2026-03-20T12:00:00.123456789Z")


if __name__ == "__main__":
    unittest.main()
