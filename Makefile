PREFIX ?= /usr/local
BINDIR  = $(PREFIX)/bin
LIBDIR  = $(PREFIX)/lib/cnb
VERSION = $(shell cat VERSION)

SCRIPTS = bin/cnb bin/board bin/swarm bin/dispatcher bin/dispatcher-watchdog bin/init

# All python sources (bin + lib)
PY_SOURCES = bin/board bin/swarm bin/dispatcher bin/dispatcher-watchdog bin/init lib/ tests/

.PHONY: all install uninstall test lint typecheck format check ci clean version

all: check

check: lint test

ci: lint typecheck test

lint:
	@echo "=== ruff ==="
	ruff check $(PY_SOURCES)
	@echo ""
	@echo "=== shellcheck ==="
	shellcheck -s bash -S warning bin/cnb
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

version:
	@echo $(VERSION)
