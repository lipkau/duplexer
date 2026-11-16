# Duplexer

Interleaves manually duplex-scanned PDFs. It runs as a container, watches `/ingest`, and writes the merged PDF to
`/completed`; paperless-ngx is the main consumer. `README.md` covers configuration and deployment.

A scan holds all fronts, then all backs in reverse: `F1 … Fn, Bn … B1`. The output is `F1, B1, F2, B2, … Fn, Bn`.

## Validate

Run `make fmt-check && make lint && make lint-md && make test-ci` before committing; CI runs the same targets.
`make test-ci` skips the slow performance tests (`@pytest.mark.slow`); `make test-performance` runs only those, and
`make test` runs everything. `make help` lists the other targets.

## Processing rules

These protect users' scans, so keep them when changing `interleave.py`, `io_utils.py`, `watcher.py` or `cli.py`:

- Write output to a temporary file and rename it into place. Never leave a partial PDF in `/completed`.
- Archive the original only after the output exists. A file that fails goes to `/ingest/failed` with a log line naming
  the file and the reason.
- Process a file only once it is stable (size unchanged for `FILE_STABILITY_SECONDS`, or its `.ready` file exists in
  ready-file mode). Never process a `.ready` file as a PDF.
- Never reprocess a completed file: a restart in the middle of a run must not create duplicates.
- Keep page sizes, rotations and metadata (title, author, creator).
- Stream pages; don't hold every page of a large PDF in memory at once.
- Watching is event-driven (watchdog plus timers). Polling is only the fallback for filesystems without events.
- Raise `DuplexError` or a subclass such as `InvalidPageCountError` for bad input.

## Code layout

- `interleave.py`: PDF logic only, no file handling beyond reading and writing.
- `io_utils.py`: stability checks, atomic writes, path helpers.
- `watcher.py`: directory watching.
- `cli.py`: the Click CLI and environment variables.

The paths `/ingest` and `/completed` are fixed. Everything else is an environment variable with a default.
A new option needs all of: the `ENV` default in the `Dockerfile`, loading in `cli.py`, and a row in the README's
configuration table.

## Tests

Generate test PDFs with reportlab in fixtures (`tests/conftest.py`); don't commit binary PDFs.
Cover odd page counts, empty and corrupt files, and files that are still being written.

## Commits

Conventional Commits, such as `fix(watcher): wait for the ready file before reading`.

## Images

CI publishes `ghcr.io/lipkau/duplexer`; the workflows in `.github/workflows/` define the tags.
This repository only publishes images. The deployment lives in `lipkau/home.lab`.
