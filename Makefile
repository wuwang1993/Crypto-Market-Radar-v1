.PHONY: install run test lint clean status logs

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

install:
	@echo "==> Installing dependencies ..."
	$(PIP) install --quiet -e .

run:
	$(PYTHON) -m src.main

test:
	$(PYTHON) -m py_compile $$(find src -name '*.py')

lint:
	$(PYTHON) -m flake8 src/ --max-line-length=120 || true

clean:
	find src -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find src -name '*.pyc' -delete 2>/dev/null || true
	rm -rf .venv

status:
	@systemctl status crypto-radar 2>/dev/null || echo "systemd service not active"

logs:
	@journalctl -u crypto-radar -f -n 50 2>/dev/null || echo "Check logs/ directory"

shell:
	$(PYTHON) -c "from src.indicators import IndicatorSnapshot; from src.state.engine import evaluate_state; print('Ready.')"
