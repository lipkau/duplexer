# Stage 1: Runtime image (the only published image)
FROM python:3.15-alpine AS runtime

# OCI image labels
LABEL org.opencontainers.image.title="Duplexer" \
  org.opencontainers.image.description="PDF interleaving service for manual duplex scanning" \
  org.opencontainers.image.url="https://github.com/lipkau/duplexer" \
  org.opencontainers.image.source="https://github.com/lipkau/duplexer" \
  org.opencontainers.image.documentation="https://github.com/lipkau/duplexer/blob/main/README.md" \
  org.opencontainers.image.licenses="MIT" \
  org.opencontainers.image.vendor="Oliver Lipkau"

# Python environment configuration
ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=/app \
  PIP_NO_CACHE_DIR=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Copy dependency file first for better layer caching
COPY pyproject.toml ./

# Copy application source code
COPY src/ ./src/

# Install package (non-editable for production). pip is only needed for this step, so
# remove it afterwards to keep pip and the packages it vendors out of the image.
RUN pip install --no-cache-dir --disable-pip-version-check --no-compile . \
  && pip uninstall -y pip

# Create non-root user and volume mount points
RUN addgroup -S -g 1000 appuser && \
  adduser -S -D -H -u 1000 -G appuser -s /sbin/nologin appuser && \
  mkdir -p /ingest /completed && \
  chown -R appuser:appuser /ingest /completed /app

# Switch to non-root user
USER appuser

# Set environment defaults
ENV SCAN_GLOB=*.pdf \
  FILE_STABILITY_SECONDS=5.0 \
  LOG_LEVEL=INFO \
  REVERSE_BACKS=true \
  INSERT_BLANK_LASTBACK=false \
  OUTPUT_SUFFIX=.duplex \
  REQUIRE_READY_FILE=false

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import sys; import os; from pathlib import Path; sys.exit(0 if Path('/ingest').is_dir() and Path('/completed').is_dir() else 1)"

# Run watcher by default
ENTRYPOINT ["python", "-m", "duplexer"]
CMD ["watch"]

# Stage 2: Testing image for CI (never published)
FROM runtime AS testing

USER root

# The runtime stage has no pip, so bootstrap it from the standard library. Some dev tools
# (PyYAML, via pre-commit) have no wheels for this Python yet and need a compiler.
RUN apk add --no-cache build-base
COPY . ./
RUN python -m ensurepip \
  && python -m pip install --no-cache-dir .[dev]

RUN python -m pytest -m "not slow"

# Default to runtime stage
FROM runtime
