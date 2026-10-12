PYTHON  ?= python3
PIP     ?= pip3
MAP     ?= maps/challenger/01_the_impossible_dream.txt
ARGS    ?=

.PHONY: install run debug clean lint lint-strict test

install:
	$(PIP) install --break-system-packages -r requirements.txt

run:
	$(PYTHON) main.py $(MAP) $(ARGS)

debug:
	$(PYTHON) -m pdb main.py $(MAP) $(ARGS)

lint:
	flake8 .
	mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports \
		--disallow-untyped-defs --check-untyped-defs

lint-strict:
	flake8 .
	mypy . --strict

test:
	$(PYTHON) -m pytest tests/ -q

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .mypy_cache .pytest_cache
