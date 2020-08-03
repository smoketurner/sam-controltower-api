#!/usr/bin/env python
# -*- coding: utf-8 -*-

import boto3


class STS:
    def __init__(self) -> None:
        self.client = boto3.client("sts")

    def assume_role(self, role_arn, role_session_name):
        response = self.client.assume_role(
            RoleArn=role_arn, RoleSessionName=role_session_name
        )
        return boto3.session.Session(
            aws_access_key_id=response["Credentials"]["AccessKeyId"],
            aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
            aws_session_token=response["Credentials"]["SessionToken"],
        )
