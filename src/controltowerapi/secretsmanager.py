#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
from typing import Optional

from aws_lambda_powertools import Logger
import boto3
import botocore

logger = Logger(child=True)

__all__ = ["SecretsManager"]


class SecretsManager:
    def __init__(self) -> None:
        self.client = boto3.client("secretsmanager")

    def get_secret_value(self, secret_id: str, key: str = None) -> Optional[str]:
        try:
            response = self.client.get_secret_value(SecretId=secret_id)
        except botocore.exceptions.ClientError as error:
            logger.exception(f"Unable to get secret value for {secret_id}")
            return None

        secretstring = response["SecretString"]
        if not key:
            return secretstring

        try:
            data = json.loads(secretstring)
        except json.decoder.JSONDecodeError:
            logger.exception("SecretString is not valid JSON")
            return None

        return data.get(key)
