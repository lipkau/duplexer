# Duplexer

[![CI](https://github.com/lipkau/duplexer/actions/workflows/validate-and-publish.yml/badge.svg)][ci]
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)][license]
[![GitHub Release](https://img.shields.io/github/v/release/lipkau/duplexer)][release]
[![Container Image](https://img.shields.io/badge/container-ghcr.io-blue)][container]
[![Works with paperless-ngx](https://img.shields.io/badge/works%20with-paperless--ngx-blue)][paperless]

[ci]:
  https://github.com/lipkau/duplexer/actions/workflows/validate-and-publish.yml
[license]: https://opensource.org/licenses/MIT
[release]: https://github.com/lipkau/duplexer/releases
[container]: https://github.com/lipkau/duplexer/pkgs/container/duplexer
[paperless]: https://github.com/paperless-ngx/paperless-ngx

A Docker service that automatically interleaves manually duplex-scanned PDFs.

## Why?

When scanning documents on a scanner without auto-duplex, you scan all front pages
first, then flip the stack and scan all back pages. The back pages come out in
reverse order. Duplexer automatically interleaves these pages into the correct order.

**Input:** F1, F2, F3, ..., Fn, Bn, B(n-1), ..., B1
**Output:** F1, B1, F2, B2, F3, B3, ..., Fn, Bn

## Features

- Automatic interleaving of front and back pages
- Continuous directory watching with file stability checks
- Atomic writes - no partial files
- Idempotent - won't reprocess already-completed files
- Handles odd page counts (insert blank page or move to failed)
- Flexible file detection (stability-based or .ready sidecar files)
- Docker-ready with health checks

## Workflow

1. Drop your scanned PDFs in `/ingest`
2. Duplexer detects new files and waits for stability (default 5 seconds)
3. Pages are interleaved and written to `/completed`
4. Original is archived to `/ingest/archive`

## Quick Start with Docker

Pull and run:

```bash
docker run -d \
  -v /path/to/scans:/ingest \
  -v /path/to/output:/completed \
  -e LOG_LEVEL=INFO \
  --name duplexer \
  ghcr.io/lipkau/duplexer:latest
```

**Available tags:**

- `latest` — Stable release (semver tags only)
- `dev` — Development build from main
- `vX.X.X` — Specific versions (e.g., `v1.0.0`)
- `vX` — Major versions (e.g., `v1`)

For Docker Compose examples (including paperless-ngx integration), see [`docker-compose.examples.md`](docker-compose.examples.md).

## Configuration

### Directory Paths

Duplexer uses hardcoded paths inside the container. Mount your directories via Docker:

| Path              | Purpose                          | Mount                           |
| ----------------- | -------------------------------- | ------------------------------- |
| `/ingest`         | Input directory for new PDFs     | `-v /path/to/scans:/ingest`     |
| `/completed`      | Output directory for processed   | `-v /path/to/output:/completed` |
| `/ingest/archive` | Successfully processed originals | (auto-created)                  |
| `/ingest/failed`  | Invalid or failed PDFs           | (auto-created)                  |

### Environment Variables

| Variable                 | Default   | Description                                                        |
| ------------------------ | --------- | ------------------------------------------------------------------ |
| `LOG_LEVEL`              | `INFO`    | Logging: `DEBUG`, `INFO`, `WARNING`, `ERROR`                       |
| `SCAN_GLOB`              | `*.pdf`   | File pattern to watch (e.g., `scan_*.pdf`, `*.PDF`)                |
| `FILE_STABILITY_SECONDS` | `5.0`     | Seconds file must remain unchanged before processing               |
| `REQUIRE_READY_FILE`     | `false`   | If `true`, only process PDFs with matching `.ready` sidecar file   |
| `REVERSE_BACKS`          | `true`    | Back pages are in reverse order (normal for manual duplex)         |
| `INSERT_BLANK_LASTBACK`  | `false`   | Insert blank page for odd counts; `false` moves to failed          |
| `OUTPUT_SUFFIX`          | `.duplex` | Suffix for output filenames (e.g., `scan.pdf` → `scan.duplex.pdf`) |

### Example with Custom Settings

```bash
docker run -d \
  -v /scans:/ingest \
  -v /output:/completed \
  -e LOG_LEVEL=DEBUG \
  -e FILE_STABILITY_SECONDS=10.0 \
  -e INSERT_BLANK_LASTBACK=true \
  -e OUTPUT_SUFFIX=.interleaved \
  --name duplexer \
  ghcr.io/lipkau/duplexer:latest
```

## Integration with paperless-ngx

See [`docker-compose.examples.md`](docker-compose.examples.md) for Docker Compose setup with paperless-ngx.
