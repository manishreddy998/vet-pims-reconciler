PY := .venv/bin/python
DBT := DBT_PROFILES_DIR=. .venv/bin/dbt
SCALE ?= 1

.PHONY: all setup data load build docs report clean

all: data load build docs report   ## generate data, load it, build + test, docs, report

setup:
	python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt

data:
	$(PY) scripts/generate.py --scale $(SCALE)

load:
	$(PY) scripts/load.py

build:
	$(DBT) seed -q && $(DBT) build && $(DBT) source freshness

docs:
	$(DBT) docs generate -q && $(PY) scripts/export_llm_catalog.py

report:
	$(PY) scripts/report.py

clean:
	rm -rf target logs warehouse.duckdb* data/raw/*
