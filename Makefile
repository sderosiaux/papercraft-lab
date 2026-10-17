PYTHON := .venv/bin/python

.PHONY: setup smoke tentacle recolor check

setup:
	git submodule update --init --recursive
	uv venv --python 3.13 .venv
	uv pip install --python $(PYTHON) -r requirements-lock.txt

smoke:
	$(PYTHON) test_pipeline.py
	$(PYTHON) finish_patterns.py

tentacle:
	$(PYTHON) build_tentacle.py
	$(PYTHON) package_tentacle.py

recolor:
	$(PYTHON) export_color.py
	$(PYTHON) package_tentacle.py

check:
	$(PYTHON) scripts/check_example.py
