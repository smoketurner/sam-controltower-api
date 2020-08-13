#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime, timezone
import hmac
import json
import os
import warnings

from aws_lambda_powertools import Logger, Metrics, Tracer
import requests

from .controltowerapi.models import AccountModel

warnings.filterwarnings("ignore", "No metrics to publish*")

tracer = Tracer()
logger = Logger()
metrics = Metrics()

SECRET_ID = os.environ["SECRET_ID"]
TOKEN = None


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: dict, context: dict) -> None:

    account_name = event.get("account", {}).get("accountName")

    try:
        account = AccountModel.get(account_name)
    except AccountModel.DoesNotExist:
        logger.error(f'Account "{account_name}" does not exist')
        return

    actions = []
    account_id = event.get("account", {}).get("accountId")
    if account_id:
        actions.append(AccountModel.account_id.set(account_id))

    ou_name = event.get("organizationalUnit", {}).get("organizationalUnitName")
    if ou_name:
        actions.append(AccountModel.ou_name.set(ou_name))

    ou_id = event.get("organizationalUnit", {}).get("organizationalUnitId")
    if ou_id:
        actions.append(AccountModel.ou_id.set(ou_id))

    state = event.get("state")
    if state:
        actions.append(AccountModel.status.set(state))

    if actions:
        actions.append(AccountModel.updated_at.set(datetime.now(timezone.utc)))

    account.update(actions=actions)
    account.refresh()

    if account.callback_url:
        print(f"Send callback to {account.callback_url}")

        data = {
            "account_name": account.account_name,
            "account_id": account.account_id,
            "ou_name": account.ou_name,
            "ou_id": account.ou_id,
            "status": account.status,
            "created_at": str(account.created_at),
        }

        payload = json.dumps(data, indent=None, sort_keys=True, separator=(",", ":"))

        headers = {}

        if account.callback_secret:
            key = str(account.callback_secret).encode()
            sig = hmac.new(key, payload.encode(), "sha1").hexdigest()
            headers["X-Signature"] = "sha1=" + sig

        response = requests.post(account.callback_url, payload=payload, headers=headers)
