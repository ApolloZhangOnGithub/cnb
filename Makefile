PREFIX ?= /usr/local
BINDIR  = $(PREFIX)/bin
LIBDIR  = $(PREFIX)/lib/cnb
VERSION = $(shell cat VERSION)

SCRIPTS = bin/cnb bin/board bin/swarm bin/dispatcher bin/dispatcher-watchdog bin/init

# All python sources (bin + lib)
PY_SOURCES = bin/board bin/swarm bin/dispatcher bin/dispatcher-watchdog bin/init bin/check-site-docs bin/check-registry-pr-guard lib/ tests/

.PHONY: all install uninstall test lint typecheck format check ci clean version sync-version check-version check-docs check-registry-guard

all: check

check: lint test check-docs

ci: lint typecheck test check-version check-docs check-registry-guard

lint:
	@echo "=== ruff ==="
	ruff check $(PY_SOURCES)
	@echo ""
	@echo "=== shellcheck ==="
	@if command -v shellcheck >/dev/null 2>&1; then \
		shellcheck -s bash -S warning bin/cnb; \
	else \
		echo "SKIP shellcheck (not installed)"; \
	fi
	@echo ""
	@echo "OK"

typecheck:
	@echo "=== mypy ==="
	mypy lib/
	@echo ""
	@echo "OK"

format:
	ruff format $(PY_SOURCES)
	ruff check --fix $(PY_SOURCES)

test:
	python3 -m pytest tests/ -v

install:
	install -d $(BINDIR)
	install -d $(LIBDIR)/bin $(LIBDIR)/lib
	install -m 755 $(SCRIPTS) $(LIBDIR)/bin/
	install -m 644 lib/*.py $(LIBDIR)/lib/
	install -m 644 schema.sql VERSION $(LIBDIR)/
	ln -sf $(LIBDIR)/bin/cnb $(BINDIR)/cnb

uninstall:
	rm -f $(BINDIR)/cnb
	rm -rf $(LIBDIR)

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/ build/ .mypy_cache/ .ruff_cache/

sync-version:
	python3 bin/sync-version

check-version:
	python3 bin/sync-version --check

check-docs:
	python3 bin/check-readme-sync
	python3 bin/check-site-docs

check-registry-guard:
	python3 bin/check-registry-pr-guard

version:
	@echo $(VERSION)
