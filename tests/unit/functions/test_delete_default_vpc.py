#!/usr/bin/env python
# -*- coding: utf-8 -*-

from dataclasses import dataclass
import os
import unittest
import warnings

from moto import mock_ec2, mock_sts
import boto3

from functions.delete_default_vpc import lambda_handler

warnings.filterwarnings("ignore", "No metrics to publish*")


@dataclass
class Context:
    function_name: str = "test"
    memory_limit_in_mb: int = 128
    invoked_function_arn: str = "arn:aws:lambda:eu-west-1:298026489:function:test"
    aws_request_id: str = "5b441b59-a550-11c8-6564-f1c833cf438c"


class TestDeleteDefaultVpc(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_SECURITY_TOKEN"] = "testing"
        os.environ["AWS_SESSION_TOKEN"] = "testing"

    def setUp(self):
        self.event = {"account": {"accountId": "123456789012"}}
        self.context = Context()

    def test_handler_no_account_id(self):
        with self.assertRaises(Exception) as cm:
            lambda_handler.handler({}, self.context)

        self.assertEqual(str(cm.exception), "Account ID not found in event")

    @mock_ec2
    @mock_sts
    def test_handler(self):
        lambda_handler.handler(self.event, self.context)

        ec2 = boto3.client("ec2")

        all_regions = [
            region["RegionName"]
            for region in ec2.describe_regions(AllRegions=True)["Regions"]
        ]

        for region in all_regions:
            ec2 = boto3.client("ec2", region_name=region)
            response = ec2.describe_vpcs()
            vpcs = response.get("Vpcs", [])
            self.assertEquals(len(vpcs), 0)


if __name__ == "__main__":
    unittest.main()
