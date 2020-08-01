#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os

from aws_lambda_powertools import Logger, Metrics, Tracer
from jsonschema import validate, ValidationError

from controltowerapi.servicecatalog import ServiceCatalog
from controltowerapi.dynamodb import DynamoDB
from responses import build_response, error_response

ACCOUNT_TABLE = os.environ["ACCOUNT_TABLE"]

tracer = Tracer()
logger = Logger()
metrics = Metrics()

dynamodb = DynamoDB()
servicecatalog = ServiceCatalog()
portfolio_id = servicecatalog.get_ct_portfolio_id()
servicecatalog.associate_principal(portfolio_id, os.environ["LAMBDA_ROLE_ARN"])
product = servicecatalog.get_ct_product()

schema = {
    "type": "object",
    "properties": {
        "AccountName": {
            "type": "string",
            "pattern": "^[a-zA-Z0-9]{3,50}$",
            "minLength": 3,
            "maxLength": 50,
        },
        "AccountEmail": {"type": "string", "format": "email"},
        "ManagedOrganizationalUnit": {"type": "string"},
        "SSOUserEmail": {"type": "string", "format": "email"},
        "SSOUserFirstName": {"type": "string"},
        "SSOUserLastName": {"type": "string"},
        "CallbackUrl": {"type": "string", "format": "uri"},
    },
    "required": [
        "AccountName",
        "AccountEmail",
        "ManagedOrganizationalUnit",
        "SSOUserEmail",
        "SSOUserFirstName",
        "SSOUserLastName",
    ],
}


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):

    if not event or "body" not in event:
        return error_response(400, "Unknown event")

    try:
        body = json.loads(event["body"])
    except ValueError:
        return error_response(400, "Unable to parse JSON body")

    try:
        validate(instance=body, schema=schema)
    except ValidationError as error:
        return error_response(400, error.message)

    parameters = {
        "AccountName": body["AccountName"],
        "AccountEmail": body["AccountEmail"],
        "ManagedOrganizationalUnit": body["ManagedOrganizationalUnit"],
        "SSOUserEmail": body["SSOUserEmail"],
        "SSOUserFirstName": body["SSOUserFirstName"],
        "SSOUserLastName": body["SSOUserLastName"],
    }

    try:
        record_id = servicecatalog.provision_product(product, parameters)
    except Exception as error:
        logger.error(f"Unable to provision product: {str(error)}")
        return error_response(500, "Unable to provision product")

    item = {
        "AccountName": body["AccountName"],
        "RecordId": record_id,
        "ManagedOrganizationalUnit": body["ManagedOrganizationalUnit"],
    }
    if "CallbackUrl" in body:
        item["CallbackUrl"] = body["CallbackUrl"]

    try:
        dynamodb.put_item(ACCOUNT_TABLE, item)
    except Exception:
        logger.error("Unable to put account in DynamoDB")

    return build_response(200, item)
