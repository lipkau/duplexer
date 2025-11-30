# Copilot Instructions for Duplexer Project

## Project Overview

This is a Python service that interleaves manually duplex-scanned PDFs.
It runs as a Docker container and watches an input directory,
processing PDFs by splitting them into front and back pages, then interleaving them in the correct order.

**Core algorithm:**

- Input: F1, F2, ..., Fn, Bn, B(n-1), ..., B1
- Output: F1, B1, F2, B2, ..., Fn, Bn

## Key Constraints

### PDF Processing

- **Never load entire PDFs into memory unnecessarily** - use streaming/iteration where possible
- **Atomic I/O only** - write to temp files, then rename to final destination
- **Preserve page properties** - maintain sizes, rotations, and metadata
- **Handle errors gracefully** - move failed files to failed/ directory with clear logging

### File Watching

- **Event-driven with timers** - watchdog events trigger, timers schedule stability checks (zero polling)
- **Stability checks are critical** - don't process files still being written
- **Idempotency** - never reprocess already-completed files
- **Two modes**: stability-based (default) or .ready-file based
- **Graceful shutdown** - handle SIGTERM/SIGINT cleanly
- **Polling fallback** - only used when watchdog unavailable (network filesystems)

### Testing

- **Always write tests for new functionality** - maintain >80% coverage
- **Use fixtures** - programmatically generate test PDFs with reportlab
- **Test edge cases**: odd pages, corrupted PDFs, empty files, concurrent access
- **Integration tests** - use temp directories to test full workflows

## Coding Style

### Python Standards

- Type hints on all public functions
- Docstrings with examples for complex logic
- Use logging (never print) with appropriate levels
- Follow PEP 8. Ruff handles formatting, import sorting, and linting (line length 100)

### Markdown Standards

- Lint all Markdown with `markdownlint-cli2` using `.markdownlint.json`
- Line length 120 (headings & code blocks also 120)
- Exclude: `node_modules`, `venv`, `.venv`
- Run via `make lint-md`

### Module Organization

- `interleave.py` - Pure PDF logic, no I/O beyond read/write
- `io_utils.py` - File operations, stability checks, path helpers
- `watcher.py` - Directory watching with watchdog/polling fallback
- `cli.py` - Click CLI, environment variable loading
- Keep functions small and testable

### Error Handling

- Custom exceptions: `DuplexError`, `InvalidPageCountError`
- Log errors with context (filename, operation, details)
- Move failed files to failed/ directory
- Never leave partial outputs

## Configuration Philosophy

- **Environment variables for all runtime config** with sensible defaults
- **CLI flags override env vars** for manual operations
- **Log configuration on startup** so users can verify settings
- **Validate inputs early** - fail fast with clear messages

## Docker Best Practices

- Run as non-root user (uid 1000)
- Minimal base image (python:3.14-slim)
- Layer caching - copy pyproject.toml before code
- No pip cache in final image
- Health checks for container orchestration
- Images automatically published to GHCR on main and releases

### Docker Image Deployment

Images are automatically built and published to GitHub Container Registry (GHCR):

**On `main` branch push:**

- Tag: `dev` — Latest development build
- Available at: `ghcr.io/lipkau/duplexer:dev`

**On release tag (e.g., `v1.0.0`):**

- Tags: `v1.0.0` (full version), `v1` (major), `latest` (stable)
- Available at: `ghcr.io/lipkau/duplexer:latest`, `v1.0.0`, or `v1`

Users can deploy with:

```bash
docker pull ghcr.io/lipkau/duplexer:latest        # Stable
docker pull ghcr.io/lipkau/duplexer:dev           # Development
docker run -d \
  -v /path/to/scans:/ingest \
  -v /path/to/output:/completed \
  ghcr.io/lipkau/duplexer:latest
```

## When Making Changes

1. **Understand the full workflow** before modifying
2. **Write tests first** for new features or bug fixes
3. **Update documentation** - README, docstrings
4. **Check edge cases** - odd pages, empty dirs, missing files
5. **Test in Docker** - verify volume mounts and permissions work
6. **Consider idempotency** - what if the service restarts mid-process?

## Common Patterns

### Adding a new configuration option

1. Add to Dockerfile ENV defaults
2. Add to README configuration table
3. Load in `cli.py` with default
4. Pass through to relevant function
5. Document in function docstring

### Adding a new processing step

1. Write unit tests for the logic
2. Implement in appropriate module
3. Add integration test with temp dirs
4. Update CLI if needed
5. Document in README and docstrings

### Debugging file watching issues

1. Enable DEBUG logging
2. Check file stability settings
3. Verify glob pattern matches
4. Test with --once mode first
5. Check file permissions in volumes

## Testing Expectations

- **Unit tests** - fast, isolated, mock external dependencies
- **Integration tests** - use real temp directories and files
- **Fixtures** - generate PDFs programmatically, don't commit binary test files
- **Coverage** - aim for >80%, focus on critical paths
- **Fast feedback** - tests should run in <10 seconds total
- **Performance tests** - large PDFs (100/500/1000 pages) & memory efficiency tagged with
  `@pytest.mark.slow` and run via `make test-performance`
- **CI split** - fast tests with coverage (`make test-ci`), slow tests excluded from coverage

## Important Notes

- **Watchdog is primary** - event-driven with timer-based stability checks; polling is fallback only
- **Hardcoded paths** - `/ingest` and `/completed` are not configurable via env vars
- **Page count validation** - always check if pages can be split evenly
- **Metadata preservation** - copy title/author/creator when available
- **Ready files** - .ready files themselves should never be processed as PDFs
- **Archive before output** - move original only after successful processing
- **Performance** - stream large PDFs; avoid loading all pages at once
- **Tooling** - black & isort removed; ruff consolidates formatting + lint
- **Markdown** - Node tooling added only for Markdown lint (no runtime impact)

## Related Systems

- **paperless-ngx** - primary integration target
- **Docker/docker-compose** - deployment model
- **GitHub Actions** - CI/CD with multi-arch builds

## Useful Commands

```bash
# Development
make install          # Setup dev environment (Python + Node)
make test             # Run fast tests only
make test-ci          # Fast tests with coverage (CI parity)
make test-performance # Slow performance tests
make fmt              # Format & fix Python code (ruff)
make fmt-check        # Check formatting only
make lint             # Python lint + type check (ruff + pyright)
make lint-md          # Markdown lint

# Docker
make docker-build    # Build image
make docker-run      # Test locally

# CLI
duplexer interleave INPUT OUTPUT    # Single file
duplexer watch --once              # Process existing
duplexer watch -v                  # Continuous with debug
```

## CI Tooling Summary

GitHub Actions CI/CD pipeline with 5 jobs:

1. **quality job** (single Python 3.14):

   - Runs: `make fmt-check`, `make lint`, `make lint-md`
   - Catches formatting and code quality issues early
   - Fails fast before testing

2. **test job** (matrix: Python 3.12, 3.13, 3.14):

   - Depends on: quality job
   - Runs: `make test-ci` (fast unit/integration tests)
   - Python 3.14: Also runs `make test-performance` and uploads coverage to Codecov

3. **build job** (Docker build validation):

   - Depends on: test job
   - Runs on: all pushes and PRs
   - Builds image for validation only (no push)
   - Uses GitHub Actions cache for layer caching

4. **release-dev job** (publish dev tag):

   - Depends on: build job
   - Runs only on: main branch pushes
   - Publishes `dev` tag to GHCR
   - Uses cached layers from build job

5. **release-official job** (publish release tags):

   - Depends on: build job
   - Runs only on: semantic version tags (v*.*.*)
   - Publishes tags to GHCR:
     - `vX.X.X`: full version (e.g., v1.0.0 → 1.0.0)
     - `vX`: major version (e.g., v1.0.0 → v1)
     - `latest`: only on release tags
   - Uses cached layers from build job

**Tooling:**

- Python: ruff (format + lint), pyright (type check), pytest (testing)
- Node: markdownlint-cli2 (markdown validation)
- All steps use Makefile targets for consistency

## Adding New Tooling

1. Confirm existing tools (ruff, markdownlint) cannot cover the need
2. Add dependency to `pyproject.toml` (Python) or `package.json` (Node)
3. Create a Makefile target (`make <tool>`) and use it in CI
4. Document in README and in this instructions file
5. Keep runtime lean (avoid adding heavy, unused dependencies)
