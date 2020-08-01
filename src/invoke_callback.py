#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from aws_lambda_powertools import Logger, Metrics, Tracer

from controltowerapi.dynamodb import DynamoDB

ACCOUNT_TABLE = os.environ["ACCOUNT_TABLE"]

tracer = Tracer()
logger = Logger()
metrics = Metrics()

dynamodb = DynamoDB()


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):

    account_name = event.get("account", {}).get("accountName")
    key = {"AccountName": account_name}

    if event.get("state") != "SUCCEEDED":
        dynamodb.delete_item(ACCOUNT_TABLE, key)
        return

    item = dynamodb.get_item(ACCOUNT_TABLE, key)
    callback_url = item.get("CallbackUrl")
    if callback_url:
        print(f"Send callback to {callback_url}")

