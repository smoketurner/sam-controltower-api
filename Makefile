.PHONY: setup build deploy format

setup:
	python3 -m venv .venv
	.venv/bin/python3 -m pip install -U pip
	.venv/bin/python3 -m pip install -r requirements.txt
	.venv/bin/python3 -m pip install -r dependencies/requirements.txt

build:
	sam build -u

deploy:
	sam deploy

format:
	black .

