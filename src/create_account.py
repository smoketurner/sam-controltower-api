#!/usr/bin/env python
# -*- coding: utf-8 -*-

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging.logger import set_package_logger

set_package_logger()

tracer = Tracer()
logger = Logger()
metrics = Metrics()


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context
def lambda_handler(event, context):
    pass
