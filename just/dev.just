# Development recipes

# Bootstrap the development environment
dev:
    uv sync

# Run the CLI
run *ARGS:
    uv run pikvm-auto {{ ARGS }}

# Run tests
test *ARGS:
    uv run pytest {{ ARGS }}

# Run linter
lint:
    uv run ruff check src/ tests/

# Format code
fmt:
    uv run ruff format src/ tests/
