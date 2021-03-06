#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Dict, Any
import warnings

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
import botocore
import pynamodb

from controltowerapi.models import AccountModel
from responses import build_response, error_response, authenticate_request

warnings.filterwarnings("ignore", "No metrics to publish*")

tracer = Tracer()
logger = Logger()
metrics = Metrics()


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:

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

    try:
        account.delete(AccountModel.status == "QUEUED")
    except pynamodb.exceptions.DeleteError as error:
        logger.exception("Unable to delete account")
        if isinstance(error.cause, botocore.exceptions.ClientError):
            if (
                error.cause.response["Error"]["Code"]
                == "ConditionalCheckFailedException"
            ):
                return error_response(
                    409,
                    f'Account creation for "{account_name}" has already started and cannot be deleted',
                )
        return error_response(500, "Unable to delete account")

    return build_response(204)
