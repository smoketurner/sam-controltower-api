#!/usr/bin/env python
# -*- coding: utf-8 -*-

from aws_lambda_powertools import Logger, Metrics, Tracer

from controltowerapi.servicecatalog import ServiceCatalog
from responses import build_response, error_response

tracer = Tracer()
logger = Logger()
metrics = Metrics()

client = ServiceCatalog()


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):

    if not event or "pathParameters" not in event:
        return error_response(400, "Unknown event")

    record_id = event.get("pathParameters", {}).get("recordId")

    try:
        response = client.describe_record(record_id)
    except Exception:
        return error_response(500, "Unable to get account status")

    detail = response.get("RecordDetail", {})

    data = {
        "AccountName": detail.get("ProvisionedProductName"),
        "RecordId": detail.get("RecordId"),
        "Status": detail.get("Status"),
    }

    return build_response(200, data)
