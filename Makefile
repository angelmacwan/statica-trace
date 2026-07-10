.PHONY: lint test install

# ---------------------------------------------------------------------------
# Install dev dependencies
# ---------------------------------------------------------------------------
install:
	pip install -e ".[dev]"

# ---------------------------------------------------------------------------
# 0.1.1 — Python linting (ruff + black)
# Exits non-zero on any violation so CI can gate on this.
# ---------------------------------------------------------------------------
lint:
	ruff check .
	black --check .

# ---------------------------------------------------------------------------
# 0.1.1 — Auto-fix formatting (convenience, not used in CI)
# ---------------------------------------------------------------------------
fmt:
	ruff check --fix .
	black .

# ---------------------------------------------------------------------------
# 0.1.2 — Run full Python test suite with coverage
# ---------------------------------------------------------------------------
test:
	pytest

# ---------------------------------------------------------------------------
# Run entire validation suite locally (equivalent to the CI pipeline)
# ---------------------------------------------------------------------------
ci: lint test
	@echo "=== Running Frontend Linting ==="
	cd frontend && npm run lint
	@echo "=== Running Frontend Unit Tests ==="
	cd frontend && npm run test
	@echo "=== Running Frontend E2E Tests ==="
	cd frontend && npm run test:e2e
	@echo "=== All checks passed successfully! Ready to push. ==="

.PHONY: lint test install ci fmt
