"""Container entrypoint."""

from __future__ import annotations

import logging

from .config import load_config
from .management_client import ManagementClient
from .snapshot_store import SnapshotStore
from .service import UsagePersistService


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    config = load_config()
    service = UsagePersistService(
        client=ManagementClient(
            base_url=config.management_url,
            management_key=config.management_key,
            timeout_seconds=config.timeout_seconds,
        ),
        store=SnapshotStore(config.snapshot_path),
        interval_seconds=config.interval_seconds,
        retry_attempts=config.retry_attempts,
        retry_base_delay_seconds=config.retry_base_delay_seconds,
        retry_max_delay_seconds=config.retry_max_delay_seconds,
    )
    service.run()


if __name__ == "__main__":
    main()
