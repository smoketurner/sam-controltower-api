#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os

from aws_lambda_powertools import Logger, Metrics, Tracer
from jsonschema import validate, ValidationError

from controltowerapi.servicecatalog import ServiceCatalog
from responses import build_response, error_response

tracer = Tracer()
logger = Logger()
metrics = Metrics()

client = ServiceCatalog()
portfolio_id = client.get_ct_portfolio_id()
client.associate_principal(portfolio_id, os.environ["LAMBDA_ROLE_ARN"])
product = client.get_ct_product()

schema = {
    "type": "object",
    "properties": {
        "AccountName": {"type": "string"},
        "AccountEmail": {"type": "string"},
        "ManagedOrganizationalUnit": {"type": "string"},
        "SSOUserEmail": {"type": "string"},
        "SSOUserFirstName": {"type": "string"},
        "SSOUserLastName": {"type": "string"},
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
@logger.inject_lambda_context
def lambda_handler(event, context):

    if not event or "body" not in event:
        return error_response(400, "Unknown event")

    try:
        parameters = json.loads(event["body"])
    except ValueError:
        return error_response(400, "Unable to parse JSON body")

    try:
        validate(instance=parameters, schema=schema)
    except ValidationError as error:
        return error_response(400, error.message)

    logger.info(parameters)

    try:
        record_id = client.provision_product(product, parameters)
    except Exception as error:
        logger.error(f"Unable to provision product: {str(error)}")
        return error_response(500, "Unable to provision product")

    data = {"record_id": record_id}

    return build_response(200, data)
