# Duplexer

A Python service that interleaves manually duplex-scanned PDFs before import into paperless-ngx
or other document management systems.

## Overview

When scanning documents on a scanner without auto-duplex, you scan all front pages first,
then flip the stack and scan all back pages. The back pages come out in reverse order.
This service automatically interleaves these pages into the correct order.

**Input page order:** F1, F2, F3, ..., Fn, Bn, B(n-1), ..., B1
**Output page order:** F1, B1, F2, B2, F3, B3, ..., Fn, Bn

## Features

- **Automatic interleaving** of front and back pages
- **Continuous directory watching** with file stability checks
- **Atomic writes** - no partial files
- **Idempotent** - won't reprocess already-completed files
- **Configurable** via environment variables
- **Docker-ready** with non-root user and health checks
- **Flexible file detection** - stability-based or .ready file
- **Handles edge cases** - odd pages, blank page insertion, corrupted PDFs

## Quick Start

### Using Docker

The container image is automatically built and published to GitHub Container Registry (GHCR)
on every push to `main` and on release tags.

**Available tags:**

- `dev` — Latest development build from main branch
- `latest` — Latest stable release
- `vX.X.X` — Specific release versions (e.g., `v1.0.0`, `v1.1.0`)
- `X.X` — Major.minor versions (e.g., `1.0`, `1.1`)

**Pull and run:**

```bash
# Pull the latest stable image
docker pull ghcr.io/lipkau/duplexer:latest

# Or pull the latest development build
docker pull ghcr.io/lipkau/duplexer:dev

# Run with local directories
docker run -d \
  -v /path/to/scans:/ingest \
  -v /path/to/completed:/completed \
  -e LOG_LEVEL=INFO \
  --name duplexer \
  ghcr.io/lipkau/duplexer:latest
```

**Authentication (if needed):**

If the repository is private, authenticate with GitHub:

```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_USERNAME --password-stdin
docker pull ghcr.io/lipkau/duplexer:latest
```

### Using Docker Compose

```yaml
version: '3.8'

services:
  duplexer:
    image: ghcr.io/lipkau/duplexer:latest
    volumes:
      - ./scans:/ingest
      - ./completed:/completed
    environment:
      LOG_LEVEL: INFO
      REVERSE_BACKS: "true"
      INSERT_BLANK_LASTBACK: "false"
      FILE_STABILITY_SECONDS: "5.0"
    restart: unless-stopped
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - >-
          import pathlib;
          exit(0 if pathlib.Path('/ingest').is_dir()
          and pathlib.Path('/completed').is_dir() else 1)
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 5s
```

### Local Installation

```bash
# Clone repository
git clone https://github.com/lipkau/duplexer.git
cd duplexer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install
pip install -e ".[dev]"

# Run watcher
duplexer watch

# Or process single file
duplexer interleave input.pdf output.pdf
```

## Configuration

### Directory Paths

The service uses **hardcoded paths** inside the container. Configure these via Docker volume mounts:

| Path              | Purpose                                         | Mount Example                   |
| ----------------- | ----------------------------------------------- | ------------------------------- |
| `/ingest`         | Input directory for new PDFs                    | `-v /path/to/scans:/ingest`     |
| `/completed`      | Output directory for processed PDFs             | `-v /path/to/output:/completed` |
| `/ingest/archive` | Successfully processed originals (auto-created) | *(subdirectory of /ingest)*     |
| `/ingest/failed`  | Invalid or failed PDFs (auto-created)           | *(subdirectory of /ingest)*     |

### Environment Variables

Runtime behavior is controlled via environment variables:

| Variable                 | Default   | Description                                                                   |
| ------------------------ | --------- | ----------------------------------------------------------------------------- |
| `LOG_LEVEL`              | `INFO`    | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`                        |
| `SCAN_GLOB`              | `*.pdf`   | File pattern to watch (e.g., `scan_*.pdf`, `*.PDF`)                           |
| `FILE_STABILITY_SECONDS` | `5.0`     | Seconds file size must remain unchanged before processing                     |
| `REQUIRE_READY_FILE`     | `false`   | If `true`, only process PDFs with matching `.ready` sidecar file              |
| `REVERSE_BACKS`          | `true`    | Back pages are in reverse order (normal for manual duplex)                    |
| `INSERT_BLANK_LASTBACK`  | `false`   | If `true`, insert blank page for odd page counts; if `false`, move to failed/ |
| `OUTPUT_SUFFIX`          | `.duplex` | Suffix added to output filename (e.g., `scan.pdf` → `scan.duplex.pdf`)        |

**Note:** Set boolean values as strings: `"true"`, `"false"`, `"1"`, `"0"`, `"yes"`, `"no"` (case-insensitive).

### CLI Options

The `watch` command supports CLI overrides for testing:

```bash
duplexer watch \
  --pattern "scan_*.pdf" \           # Override SCAN_GLOB
  --stability-seconds 10.0 \         # Override FILE_STABILITY_SECONDS
  --require-ready-file true \        # Override REQUIRE_READY_FILE
  --verbose                          # Force DEBUG logging
```

The `interleave` command (single-file mode) supports:

```bash
duplexer interleave input.pdf output.pdf \
  --reverse-backs / --no-reverse-backs \        # Override REVERSE_BACKS
  --insert-blank-lastback / --no-insert-blank-lastback \  # Override INSERT_BLANK_LASTBACK
  --verbose                                      # Force DEBUG logging
```

## Usage Examples

### CLI - Single File

```bash
# Basic interleaving
duplexer interleave scan.pdf output.pdf

# With options
duplexer interleave scan.pdf output.pdf \
  --no-reverse-backs \
  --insert-blank-lastback \
  --verbose
```

### CLI - Watch Mode

```bash
# Watch with defaults from environment
duplexer watch

# Watch with overrides
duplexer watch \
  --pattern "*.pdf" \
  --stability-seconds 10.0 \
  --verbose

# Process existing files once and exit
duplexer watch --once

# Require .ready sidecar files
duplexer watch --require-ready-file
```

### Docker with Custom Settings

```bash
docker run -d \
  -v /scans:/ingest \
  -v /completed:/completed \
  -e LOG_LEVEL=DEBUG \
  -e REVERSE_BACKS=false \
  -e INSERT_BLANK_LASTBACK=true \
  -e OUTPUT_SUFFIX=.interleaved \
  -e FILE_STABILITY_SECONDS=10.0 \
  --name duplexer \
  duplexer:latest
```

## How It Works

1. **File Detection**: Service watches `/ingest` for new PDF files using event-driven filesystem monitoring (watchdog)
2. **Stability Check**: Schedules a timer for `FILE_STABILITY_SECONDS` to ensure file is completely written
3. **Validation**: Ensures PDF is readable and not password-protected
4. **Interleaving**:
   - Split pages into fronts (first half) and backs (second half)
   - Reverse backs if `REVERSE_BACKS=true`
   - Interleave: F1, B1, F2, B2, ...
   - Handle odd pages per `INSERT_BLANK_LASTBACK` setting
5. **Output**: Write to `/completed` with atomic rename
6. **Cleanup**: Move original to `/ingest/archive`

### Handling Odd Page Counts

If a PDF has an odd number of pages:

- **`INSERT_BLANK_LASTBACK=false`** (default): File moved to `/ingest/failed`, error logged
- **`INSERT_BLANK_LASTBACK=true`**: Blank page inserted as last back page

### File Readiness Strategies

**Stability-based (default):**

- File must have unchanged size for `FILE_STABILITY_SECONDS`
- Prevents processing incomplete uploads

**Ready-file based:**

- Set `REQUIRE_READY_FILE=true`
- Only process `file.pdf` when `file.pdf.ready` exists
- Useful for scripts that create sidecar files when upload complete

## Directory Structure

```text
/ingest/                  # Input directory (hardcoded, mount via Docker)
├── scan001.pdf          # New scans appear here
├── archive/             # Successfully processed originals
└── failed/              # Invalid or odd-page PDFs

/completed/               # Output directory (hardcoded, mount via Docker)
└── scan001.duplex.pdf   # Processed output
```

## Development

### Setup

```bash
make venv
source venv/bin/activate
make install
```

### Testing

```bash
# Run tests
make test

# Run with coverage
pytest --cov=src/duplexer --cov-report=html

# Run only fast tests (skip performance tests)
pytest -m "not slow"

# Run performance tests
pytest -m slow -v -s

# View coverage
open htmlcov/index.html
```

**Performance tests** verify the service handles large PDFs efficiently:

- 100 pages: Should complete in <5 seconds
- 500 pages: Should complete in <20 seconds
- 1000 pages: Should complete in <40 seconds
- Memory efficiency: Should not load entire PDF into memory
- Concurrent processing: Should handle multiple files without issues

Performance tests are marked with `@pytest.mark.slow` and can be skipped for faster test runs.

### Code Quality

```bash
# Format code
make fmt

# Lint and type check
make lint

# Individual commands
ruff format src tests           # Format with ruff
ruff check src tests            # Lint with ruff
pyright                         # Type check with pyright
```

### Building

```bash
# Python package
make build

# Docker image
make docker-build

# Test locally
make docker-run
```

## Troubleshooting

### Files not being processed

- Check `LOG_LEVEL=DEBUG` to see detailed file detection logs
- Verify `FILE_STABILITY_SECONDS` - files may need more time to stabilize
- Check file permissions in Docker volumes
- Verify files match `SCAN_GLOB` pattern

### "Page count is odd" errors

- Set `INSERT_BLANK_LASTBACK=true` to automatically add blank pages
- Or manually ensure even page counts before scanning backs

### Password-protected PDFs

- Service cannot process encrypted PDFs
- These will be moved to `/ingest/failed`
- Remove password before scanning or use `qpdf --decrypt`

### Already processed files

- Service tracks processed files to avoid duplicates
- Checks if output exists and is newer than input
- Checks if original exists in archive
- Delete output or move from archive to reprocess

## Integration with paperless-ngx

```yaml
# docker-compose.yml
services:
  duplexer:
    image: ghcr.io/OWNER/duplexer:latest
    volumes:
      - /scans:/ingest
      - /paperless-consume:/completed
    environment:
      OUTPUT_SUFFIX: ""  # No suffix, paperless will consume directly

  paperless:
    image: ghcr.io/paperless-ngx/paperless-ngx:latest
    volumes:
      - /paperless-consume:/usr/src/paperless/consume
    # ... other paperless config
```

Workflow:

1. Scan documents → `/scans/`
2. Duplexer interleaves → `/paperless-consume/`
3. Paperless-ngx auto-imports from consume directory

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure `make test` and `make lint` pass
5. Submit a pull request

## Acknowledgments

- Uses [pypdf](https://github.com/py-pdf/pypdf) for PDF manipulation
- Uses [watchdog](https://github.com/gorakhargosh/watchdog) for file system monitoring
- Built for [paperless-ngx](https://github.com/paperless-ngx/paperless-ngx) integration
