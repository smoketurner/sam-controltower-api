#!/usr/bin/env python
# -*- coding: utf-8 -*-

import warnings

from aws_lambda_powertools import Logger, Metrics, Tracer

from controltowerapi.models import AccountModel

warnings.filterwarnings("ignore", "No metrics to publish*")

tracer = Tracer()
logger = Logger()
metrics = Metrics()


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):

    account_name = event.get("account", {}).get("accountName")

    try:
        account = AccountModel.get(account_name)
    except AccountModel.DoesNotExist:
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
        actions.append(AccountModel.state.set(state))

    account.update(actions=actions)

    if account.callback_url:
        print(f"Send callback to {account.callback_url}")

