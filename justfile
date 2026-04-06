precommit := `pre-commit install`

default:
  just -l
  echo "{{precommit}}"

# Install in editable mode with dev deps
install:
    pip install -e ".[dev]"

# Initialize or reset the database
init-db:
    python scripts/init_db.py

# Run all processes (bot + web)
run:
    python scripts/run_all.py

# Run the Discord bot only
bot:
    python scripts/run_bot.py

# Run the Flask web app only
web:
    python scripts/run_web.py

# Run all tests
test:
    pytest

# Run a specific test file
test-file file:
    pytest {{file}}

# Run tests matching a name pattern
test-match pattern:
    pytest -k {{pattern}}

# Run tests with coverage
test-cov:
    pytest --cov=quiver --cov-report=term-missing

# Format code
fmt:
    black src/ tests/ scripts/
    isort src/ tests/ scripts/

# Lint code
lint:
    black --check src/ tests/ scripts/
    isort --check src/ tests/ scripts/
    flake8 src/ tests/ scripts/

# Run pre-commit hooks on all files
check:
    pre-commit run --all-files
