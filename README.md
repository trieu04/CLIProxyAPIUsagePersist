# CLIProxyAPI Usage Persist

[![Docker Hub](https://img.shields.io/badge/docker%20hub-trieu04%2Fcli--proxy--api--usage--persist-2496ED?logo=docker&logoColor=white)](https://hub.docker.com/r/trieu04/cli-proxy-api-usage-persist)
[![Docker Image Version](https://img.shields.io/docker/v/trieu04/cli-proxy-api-usage-persist?sort=semver&label=image)](https://hub.docker.com/r/trieu04/cli-proxy-api-usage-persist/tags)
[![Docker Pulls](https://img.shields.io/docker/pulls/trieu04/cli-proxy-api-usage-persist)](https://hub.docker.com/r/trieu04/cli-proxy-api-usage-persist)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

`CLIProxyAPI Usage Persist` is a small Python service that keeps CLIProxyAPI usage data durable across restarts. It periodically exports usage data from a CLIProxyAPI instance, merges that export with a local persisted snapshot, and imports the merged snapshot back only when the merged result is fuller than the server copy.

## Features

- Works with CLIProxyAPI management endpoints over HTTP.
- Persists usage data locally in a durable JSON snapshot.
- Rebuilds totals from deduplicated request details instead of trusting incoming aggregates.
- Performs one reconcile pass at startup, then repeats on a configurable interval.
- Avoids unnecessary imports by only writing back when the merged snapshot contains more unique usage details.

## Requirements

The target CLIProxyAPI instance must expose management endpoints and usage statistics:

```yaml
usage-statistics-enabled: true

remote-management:
  secret-key: your-shared-secret
  allow-remote: true
```

Notes:

- `remote-management.secret-key` is required for management endpoints to exist.
- `remote-management.allow-remote: true` is required when this service runs outside the main CLIProxyAPI process.
- Keep `CLIPROXYAPI_BASE_URL` aligned with your network topology. If both services run in the same Docker network, use the service hostname.

## Quick start with Docker Compose

1. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

2. Update at least these values in `.env`:

   - `CLIPROXYAPI_BASE_URL`
   - `CLIPROXYAPI_MANAGEMENT_KEY`

3. Start the service:

   ```bash
   docker compose up -d
   ```

The included `docker-compose.yml` uses the published Docker Hub image `trieu04/cli-proxy-api-usage-persist:latest` and mounts a named volume at `/data`, so `usage-snapshot.json` survives container restarts.

## Docker image

Use either the moving `latest` tag or a versioned release tag:

```bash
docker pull trieu04/cli-proxy-api-usage-persist:latest
docker pull trieu04/cli-proxy-api-usage-persist:v0.1.0
```

Example:

```bash
docker run --rm \
  -e CLIPROXYAPI_BASE_URL=http://your-cli-proxy-api:8317 \
  -e CLIPROXYAPI_MANAGEMENT_KEY=your-management-secret \
  -v usage-persist-data:/data \
  trieu04/cli-proxy-api-usage-persist:latest
```

## Environment variables

Copy `.env.example` to `.env` and fill in the values.

| Variable | Required | Default | Description |
|---|---|---:|---|
| `CLIPROXYAPI_BASE_URL` | yes | none | CLIProxyAPI base URL. `http://host:8317`, `host:8317`, and `.../v0/management` all work. |
| `CLIPROXYAPI_MANAGEMENT_KEY` | yes | none | Shared management secret sent as a Bearer token. |
| `USAGE_SNAPSHOT_PATH` | no | `/data/usage-snapshot.json` | Atomic snapshot file path. |
| `SYNC_INTERVAL_SECONDS` | no | `3600` | Period between reconcile cycles after startup. |
| `HTTP_TIMEOUT_SECONDS` | no | `15` | Per-request timeout. |
| `RETRY_ATTEMPTS` | no | `4` | Total attempts for transient failures. |
| `RETRY_BASE_DELAY_SECONDS` | no | `1` | Base exponential backoff delay. |
| `RETRY_MAX_DELAY_SECONDS` | no | `8` | Maximum backoff delay. |

## Local development

Run locally without Docker:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cliproxyapi-usage-persist
```

Build a local image manually if you want to test changes before publishing:

```bash
docker build -t cliproxyapi-usage-persist:dev .
```

Then run that local image directly:

```bash
docker run --rm \
  -e CLIPROXYAPI_BASE_URL=http://your-cli-proxy-api:8317 \
  -e CLIPROXYAPI_MANAGEMENT_KEY=your-management-secret \
  -v usage-persist-data:/data \
  cliproxyapi-usage-persist:dev
```

## How it works

- Console entrypoint: `cliproxyapi-usage-persist`
- Module entrypoint: `python -m src`
- Bootstrap path: `src/main.py`
- Config loader: `src/config.py`
- Sync loop: `src/service.py`
- Management API client: `src/management_client.py`

At startup, the service loads environment-backed config, normalizes the CLIProxyAPI management URL, exports the current usage snapshot, merges it with the persisted local snapshot, saves the merged result locally, and imports back to CLIProxyAPI only when the merged snapshot contains more deduplicated request details than the exported snapshot. After the startup reconcile, it repeats the same cycle every `SYNC_INTERVAL_SECONDS` seconds.

## Merge semantics

- Dedup dimensions mirror the Go server merge key: API name, model name, timestamp, source, auth index, failed flag, and token fields.
- `latency_ms` is intentionally ignored for dedup.
- Empty model names become `unknown`, negative latency becomes `0`, and token totals are recomputed the same way as the server.
- “Fuller” means the merged snapshot contains more unique request details after server-compatible dedup than the latest export from CLIProxyAPI.

## Testing

```bash
python -m unittest discover -s tests -v
```

## License

This project is licensed under the MIT License. See [LICENSE](./LICENSE).
