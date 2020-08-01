.PHONY: setup build deploy format invoke

setup:
	python3 -m venv .venv
	.venv/bin/pip3 install -r requirements.txt
	.venv/bin/pip3 install -r src/requirements.txt

build:
	sam build -u

deploy:
	sam deploy

format:
	black .

invoke:
	sam local invoke CreateAccountLambdaFunction --profile root-admin -e events/create_account.json
