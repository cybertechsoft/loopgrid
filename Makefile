# LoopGrid Makefile

.PHONY: help install run demo test clean build

help:
	@echo "LoopGrid - Control Plane for AI Decision Reliability"
	@echo ""
	@echo "Commands:"
	@echo "  make install   Install dependencies"
	@echo "  make run       Start the server"
	@echo "  make demo      Run the demo script"
	@echo "  make test      Run tests"
	@echo "  make clean     Remove generated files"
	@echo "  make build     Build packages for distribution"

install:
	pip install -r requirements.txt

run:
	python run_server.py

demo:
	python test_demo.py

test:
	python -m pytest tests/ -v

clean:
	rm -rf __pycache__ .pytest_cache *.egg-info dist build
	rm -f *.db test_loopgrid.db
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build:
	python -m build

publish-pypi:
	twine upload dist/*

publish-npm:
	cd sdk/javascript && npm publish --access public
