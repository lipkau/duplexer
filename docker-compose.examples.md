# Docker Compose Examples for Duplexer

This directory contains example Docker Compose configurations for different use cases.

## Basic Example

```yaml
# docker-compose.yml
version: '3.8'

services:
  duplexer:
    image: ghcr.io/lipkau/duplexer:latest
    container_name: duplexer
    restart: unless-stopped
    volumes:
      - ./scans:/ingest
      - ./completed:/completed
    environment:
      SCAN_GLOB: "*.pdf"
      FILE_STABILITY_SECONDS: "5.0"
      LOG_LEVEL: INFO
```

## Integration with paperless-ngx

```yaml
# docker-compose.paperless.yml
version: '3.8'

services:
  duplexer:
    image: ghcr.io/lipkau/duplexer:latest
    container_name: duplexer
    restart: unless-stopped
    volumes:
      - ./scans:/ingest
      - paperless-consume:/completed
    environment:
      OUTPUT_SUFFIX: ""  # No suffix for paperless
      LOG_LEVEL: INFO
    depends_on:
      - paperless

  paperless:
    image: ghcr.io/paperless-ngx/paperless-ngx:latest
    container_name: paperless
    restart: unless-stopped
    volumes:
      - paperless-data:/usr/src/paperless/data
      - paperless-media:/usr/src/paperless/media
      - paperless-consume:/usr/src/paperless/consume
      - ./export:/usr/src/paperless/export
    environment:
      PAPERLESS_REDIS: redis://broker:6379
      PAPERLESS_DBHOST: db
      # Add other paperless config here
    depends_on:
      - db
      - broker

  broker:
    image: docker.io/library/redis:7
    restart: unless-stopped

  db:
    image: docker.io/library/postgres:15
    restart: unless-stopped
    volumes:
      - paperless-pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: paperless
      POSTGRES_USER: paperless
      POSTGRES_PASSWORD: paperless

volumes:
  paperless-data:
  paperless-media:
  paperless-consume:
  paperless-pgdata:
```

## Advanced Configuration

```yaml
# docker-compose.advanced.yml
version: '3.8'

services:
  duplexer:
    image: ghcr.io/lipkau/duplexer:latest
    container_name: duplexer
    restart: unless-stopped
    volumes:
      - ./scans:/ingest
      - ./completed:/completed
    environment:
      # Extended stability check for slow networks or large files
      FILE_STABILITY_SECONDS: "10.0"

      # Require .ready sidecar files (useful for scripted uploads)
      REQUIRE_READY_FILE: "true"

      # Insert blank pages for odd counts
      INSERT_BLANK_LASTBACK: "true"

      # Custom output naming
      OUTPUT_SUFFIX: ".interleaved"

      # Debug logging (shows file detection events and timer scheduling)
      LOG_LEVEL: DEBUG

      # Backs are NOT reversed (unusual for most scanners)
      REVERSE_BACKS: "false"
    healthcheck:
      test: ["CMD", "python", "-c", "import os; exit(0 if os.path.exists('/ingest') else 1)"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 5s
```

## Usage

```bash
# Start with default config
docker compose up -d

# Start with specific config file
docker compose -f docker-compose.paperless.yml up -d

# View logs
docker compose logs -f duplexer

# Stop
docker compose down

# Restart
docker compose restart duplexer
```

## Directory Setup

Before starting, create the necessary directories:

```bash
mkdir -p scans completed
chmod 755 scans completed
```

## Testing

To test the service:

1. Start the container:

   ```bash
   docker compose up -d
   ```

2. Copy a test PDF to the scans directory:

   ```bash
   cp test-scan.pdf scans/
   ```

3. Wait for file stability (default 5 seconds), then check:

   ```bash
   ls -la completed/
   ls -la scans/archive/
   ```

4. View logs:

   ```bash
   docker compose logs -f duplexer
   ```
