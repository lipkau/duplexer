.PHONY: help venv install fmt fmt-check lint lint-md test test-ci test-performance build docker-build docker-run docker-push clean clean-dev

help:
	@echo "Available targets:"
	@echo "  venv              - Create virtual environment"
	@echo "  install           - Install package with dev dependencies"
	@echo "  fmt               - Format code with ruff"
	@echo "  fmt-check         - Check code formatting without changes"
	@echo "  lint              - Run ruff and pyright"
	@echo "  lint-md           - Lint markdown files"
	@echo "  test              - Run pytest (fast tests only)"
	@echo "  test-ci           - Run tests with coverage for CI"
	@echo "  test-performance  - Run performance tests"
	@echo "  build             - Build distribution packages"
	@echo "  docker-build      - Build Docker image"
	@echo "  docker-run        - Run Docker container with dev volumes"
	@echo "  docker-push       - Push Docker image to registry"
	@echo "  clean             - Remove build artifacts and caches"

venv:
	python3 -m venv venv
	@echo "Activate with: source venv/bin/activate"

install:
	pip install -e ".[dev]"
	npm install

fmt:
	ruff format src tests
	ruff check --fix src tests

fmt-check:
	ruff format --check src tests

lint:
	ruff check src tests
	pyright

lint-md:
	npx markdownlint-cli2 "**/*.md" "#node_modules" "#venv" "#.venv"

test:
	pytest -q

test-ci:
	pytest -v -m "not slow" --cov=src/duplexer --cov-report=xml

test-performance:
	pytest -v -m slow --no-cov

build:
	python -m build

docker-build:
	docker build -t duplexer:latest .

docker-run:
	@mkdir -p dev/ingest dev/completed
	docker run --rm -it \
		-v $(PWD)/dev/ingest:/ingest \
		-v $(PWD)/dev/completed:/completed \
		-e LOG_LEVEL=DEBUG \
		duplexer:latest

docker-push:
	@echo "Configure registry and push target as needed"
	@echo "docker tag duplexer:latest ghcr.io/OWNER/REPO:latest"
	@echo "docker push ghcr.io/OWNER/REPO:latest"

clean:
	@echo "Cleaning cache..."
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	@echo "Cleaning dev/ directories..."
	rm -rf dev/ingest/*.pdf dev/ingest/archive/*.pdf dev/ingest/failed/*.pdf
	rm -rf dev/completed/*.pdf
