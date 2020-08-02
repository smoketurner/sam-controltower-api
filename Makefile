.PHONY: setup build deploy format

setup:
	python3 -m venv .venv
	.venv/bin/pip3 install -r requirements.txt
	.venv/bin/pip3 install -r dependencies/requirements.txt

build:
	sam build -u

deploy:
	sam deploy

format:
	black .

