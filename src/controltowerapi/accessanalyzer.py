#!/usr/bin/env python
# -*- coding: utf-8 -*-

from aws_lambda_powertools import Logger
import boto3
import botocore

logger = Logger()

__all__ = ["AccessAnalyzer"]


class AccessAnalyzer:
    @staticmethod
    def create_org_analyzer(account_id: str) -> None:
        """
        Create an organization IAM access analyzer in the desired account
        """
        sts = boto3.client("sts")

        role_arn = f"arn:aws:iam::{account_id}:role/AWSControlTowerExecution"
        response = sts.assume_role(RoleArn=role_arn, RoleSessionName="accessanalyzer")

        session = boto3.session.Session(
            aws_access_key_id=response["Credentials"]["AccessKeyId"],
            aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
            aws_session_token=response["Credentials"]["SessionToken"],
        )

        client = session.client("accessanalyzer")

        logger.info(
            f"Creating organizational IAM access analyzer in account {account_id}"
        )
        try:
            client.create_analyzer(
                analyzerName="OrganizationAnalyzer", type="ORGANIZATION"
            )
            logger.debug(
                f"Created organizational IAM access analyzer in account {account_id}"
            )
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] != "ConflictException":
                logger.exception(
                    f"Unable to create organization IAM access analyzer in account {account_id}"
                )
                raise error
