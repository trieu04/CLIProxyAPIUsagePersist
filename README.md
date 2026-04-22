# CLIProxyAPI Usage Persist

Python-only Dockerized service that periodically exports usage data from CLIProxyAPI, merges it with a persisted snapshot, and imports the merged snapshot back only when the merged snapshot is fuller.

## What it does

- Normalizes the configured base URL the same way as the CLIProxyAPI Management Center.
- Calls the management API with `Authorization: Bearer <key>`.
- Exports `GET /v0/management/usage/export`.
- Persists a single JSON snapshot atomically at `/data/usage-snapshot.json` by default.
- Rebuilds aggregate totals from deduped request details instead of trusting incoming totals.
- Runs startup reconcile once, then repeats every `SYNC_INTERVAL_SECONDS` seconds.
- Imports `POST /v0/management/usage/import` only when the merged snapshot has more unique request details than the server export.

## Required CLIProxyAPI settings

The target CLIProxyAPI instance must expose management endpoints and usage data:

```yaml
usage-statistics-enabled: true

remote-management:
  secret-key: your-shared-secret
  allow-remote: true
```

Notes:

- `remote-management.secret-key` is required for management endpoints to exist.
- `remote-management.allow-remote: true` is required when this container runs separately from CLIProxyAPI.
- If both containers share the same network namespace or host loopback, keep the base URL aligned with that topology.

## Environment

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

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cliproxyapi-usage-persist
```

## Docker

```bash
cp .env.example .env
docker compose up --build
```

The compose file mounts a named volume to `/data`, so `usage-snapshot.json` survives container restarts.

## Entrypoints and runtime flow

- Console entrypoint: `cliproxyapi-usage-persist`
- Module entrypoint: `python -m src`
- Bootstrap path: `src/main.py`
- Config loader: `src/config.py`
- Sync loop: `src/service.py`
- Management API client: `src/management_client.py`

At startup, the service loads environment-backed config, normalizes the CLIProxyAPI management URL, exports the current usage snapshot, merges it with the persisted local snapshot, saves the merged result locally, and imports back to CLIProxyAPI only when the merged snapshot contains more deduped request details than the exported snapshot. After the startup reconcile, it repeats the same cycle every `SYNC_INTERVAL_SECONDS` seconds.

## Merge semantics

- Dedup dimensions mirror the Go server merge key: API name, model name, timestamp, source, auth index, failed flag, and token fields.
- `latency_ms` is intentionally ignored for dedup.
- Empty model names become `unknown`, negative latency becomes `0`, and token totals are recomputed the same way as the server.
- “Fuller” means the merged snapshot contains more unique request details after server-compatible dedup than the latest export from CLIProxyAPI.

## Test

```bash
python -m unittest discover -s tests -v
```

## Published image

When a release tag like `v0.1.0` is pushed, GitHub Actions can publish a Docker image to Docker Hub with two tags:

- `latest`
- the exact Git tag, for example `v0.1.0`

Pull and run the published image like this:

```bash
docker pull <dockerhub-repo>:v0.1.0

docker run --rm \
  -e CLIPROXYAPI_BASE_URL=http://your-cli-proxy-api:8317 \
  -e CLIPROXYAPI_MANAGEMENT_KEY=your-management-secret \
  -v usage-persist-data:/data \
  <dockerhub-repo>:v0.1.0
```

Replace `<dockerhub-repo>` with your configured Docker Hub repository, for example `your-org/cliproxyapi-usage-persist`.

## Release automation

This project can ship from `.github/workflows/release.yml` with a tag-driven release flow:

1. Push a Git tag matching `v*`, for example `v0.1.0`
2. GitHub Actions builds the Docker image from the current `Dockerfile`
3. The workflow pushes `latest` and `${GITHUB_REF_NAME}` tags to Docker Hub
4. The workflow generates release notes from commits since the previous `v*` tag
5. The workflow creates a GitHub Release for the same tag

Required GitHub repository configuration:

- Repository variable: `DOCKERHUB_REPO` with the full Docker Hub repository name in `namespace/repository` format
- Repository secret: `DOCKERHUB_USERNAME`
- Repository secret: `DOCKERHUB_TOKEN`

`GITHUB_TOKEN` is provided automatically by GitHub Actions for release creation.

This workflow publishes the container image only. It does not publish the Python package anywhere, so if you use Git tags as release versions you should keep `pyproject.toml` version aligned manually.

On the first tagged release, the generated release notes include all commits reachable from that tag because there is no previous `v*` tag to diff against.

Example release commands:

```bash
git tag v0.1.0
git push origin v0.1.0
```
