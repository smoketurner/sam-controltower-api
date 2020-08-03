#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

from aws_lambda_powertools import Logger
import boto3
import botocore


boto3.set_stream_logger("", logging.INFO)
logger = Logger()


class RAM:
    def __init__(self) -> None:
        self.client = boto3.client("ram")

    def enable_sharing_with_aws_organization(self) -> None:
        logger.info("Enabling organizational sharing for RAM")
        try:
            self.client.enable_sharing_with_aws_organization()
            logger.debug("Enabled organizational access for RAM")
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] != "OperationNotPermittedException":
                logger.exception("Unable enable organization sharing for RAM")
                raise error
