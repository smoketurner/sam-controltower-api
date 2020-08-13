.PHONY: setup build deploy format test

setup:
	python3 -m venv .venv
	.venv/bin/python3 -m pip install -U pip
	.venv/bin/python3 -m pip install -r requirements-dev.txt
	.venv/bin/python3 -m pip install -r dependencies/requirements.txt

build:
	sam build -u

deploy:
	sam deploy

test:
	POWERTOOLS_TRACE_DISABLED=1 POWERTOOLS_SERVICE_NAME="Example" POWERTOOLS_METRICS_NAMESPACE="Application" .venv/bin/coverage run -m unittest discover -s ./tests
	.venv/bin/coverage report

format:
	black .

