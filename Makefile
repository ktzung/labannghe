VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PORT ?= 8765

.PHONY: setup init ingest reclassify serve test stats export prune scheduler pages

setup:
	test -d $(VENV) || python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

init:
	$(PY) -m laban.cli init

ingest:
	$(PY) -m laban.cli ingest --max-pages 30

reclassify:
	$(PY) -m laban.cli reclassify

serve:
	$(PY) -m laban.cli serve --host 127.0.0.1 --port $(PORT)

test:
	$(PY) -m unittest discover -s tests -v

stats:
	$(PY) -m laban.cli stats

export:
	$(PY) -m laban.cli export --scope all --days 30

prune:
	$(PY) -m laban.cli prune --raw-days 21 --vacuum

scheduler:
	@echo "Chạy: scripts/install_scheduler.sh  (sẽ hỏi trước khi cài launchd)"

pages:
	$(PY) scripts/build_static.py --base-url /labannghe/
