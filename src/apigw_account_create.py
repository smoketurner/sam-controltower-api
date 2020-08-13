#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime, timezone
import json
import os
import warnings

from aws_lambda_powertools import Logger, Metrics, Tracer
import boto3
import botocore
import fastjsonschema
import pynamodb

from .controltowerapi.models import AccountModel
from .responses import build_response, error_response, authenticate_request

warnings.filterwarnings("ignore", "No metrics to publish*")

ACCOUNT_QUEUE_URL = os.environ["ACCOUNT_QUEUE_URL"]

tracer = Tracer()
logger = Logger()
metrics = Metrics()

with open("./schemas/create_account.json", "r") as fp:
    VALIDATE = fastjsonschema.compile(fp.read())


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: dict, context: dict) -> dict:
    if not event or "body" not in event:
        return error_response(400, "Unknown event")

    result = authenticate_request(event)
    if result is not True:
        return result

    try:
        body = json.loads(event["body"])
    except ValueError:
        logger.exception("Unable to parse JSON body: " + event["body"])
        return error_response(400, "Unable to parse JSON body")

    try:
        VALIDATE(body)
    except fastjsonschema.JsonSchemaException as error:
        logger.exception(f"Invalid request body: {error.message}")
        return error_response(400, error.message)

    account_name = body["AccountName"]

    item = {
        "account_name": account_name,
        "account_email": body["AccountEmail"],
        "status": "QUEUED",
        "ou_name": body["ManagedOrganizationalUnit"],
        "sso_user_email": body["SSOUserEmail"],
        "sso_user_first_name": body["SSOUserFirstName"],
        "sso_user_last_name": body["SSOUserLastName"],
        "queued_at": datetime.now(timezone.utc),
    }
    if "CallbackUrl" in body:
        item["callback_url"] = body["CallbackUrl"]
    if "CallbackSecret" in body:
        item["callback_secret"] = body["CallbackSecret"]

    account = AccountModel(**item)

    try:
        account.save(AccountModel.account_name.does_not_exist())
    except pynamodb.exceptions.PutError as error:
        if isinstance(error.cause, botocore.exceptions.ClientError):
            if (
                error.cause.response["Error"]["Code"]
                == "ConditionalCheckFailedException"
            ):
                return error_response(
                    409, f'Account name "{account_name}" already exists'
                )
        return error_response(500, "Unable to store account")

    message = json.dumps(body, indent=None, separators=(",", ":"), sort_keys=True)

    logger.info(f"Sending account '{account_name}' to queue")

    sqs = boto3.client("sqs")

    try:
        sqs.send_message(
            QueueUrl=ACCOUNT_QUEUE_URL,
            MessageBody=message,
            MessageDeduplicationId=account_name,
            MessageGroupId="Accounts",
        )
        logger.debug(f"Sent account '{account_name}' to queue")
    except botocore.exceptions.ClientError as error:
        logger.exception("Unable to send message to queue")

    return build_response(202, item)
