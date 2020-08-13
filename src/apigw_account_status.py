#!/usr/bin/env python
# -*- coding: utf-8 -*-

import warnings

from aws_lambda_powertools import Logger, Metrics, Tracer

from .controltowerapi.models import AccountModel
from .responses import build_response, error_response, authenticate_request

warnings.filterwarnings("ignore", "No metrics to publish*")

tracer = Tracer()
logger = Logger()
metrics = Metrics()


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: dict, context: dict) -> dict:

    if not event or "pathParameters" not in event:
        return error_response(400, "Unknown event")

    result = authenticate_request(event)
    if result is not True:
        return result

    account_name = event.get("pathParameters", {}).get("accountName")

    try:
        account = AccountModel.get(account_name)
    except AccountModel.DoesNotExist:
        return error_response(404, "Account not found")

    data = {
        "account_name": account.account_name,
        "ou_name": account.ou_name,
        "status": account.status,
        "queued_at": str(account.queued_at),
    }

    return build_response(200, data)
