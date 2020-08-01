#!/usr/bin/env python
# -*- coding: utf-8 -*-


from aws_lambda_powertools import Logger
import boto3
import botocore


logger = Logger()


class DynamoDB:
    def __init__(self) -> None:
        self.client = boto3.client("dynamodb")

    def get_item(self, table_name: str, key: dict) -> dict:
        """
        Get an item from a DynamoDB table
        """
        try:
            response = self.client.get_item(
                TableName=table_name, Key=self.convert_to_dynamodb(key),
            )
        except botocore.exceptions.ClientError as error:
            logger.exception("Unable to get item")
            raise error

        return self.convert_from_dynamodb(response.get("Item"))

    def put_item(self, table_name: str, item: dict) -> None:
        """
        Put an item in a DynamoDB table
        """
        try:
            self.client.put_item(
                TableName=table_name,
                Item=self.convert_to_dynamodb(item),
                ConditionExpression="attribute_not_exists(AccountName)",
            )
        except botocore.exceptions.ClientError as error:
            logger.exception("Unable to put item")
            raise error

    def delete_item(self, table_name: str, key: dict) -> None:
        """
        Delete an item from a DynamoDB table
        """
        try:
            self.client.delete_item(
                TableName=table_name,
                Key=self.convert_to_dynamodb(key),
                ConditionExpress="attribute_exists(AccountName)",
            )
        except botocore.exceptions.ClientError as error:
            logger.exception("Unable to delete item")
            raise error

    @classmethod
    def convert_to_dynamodb(cls, obj: dict) -> dict:
        item = {}

        for key, value in obj.items():
            if isinstance(value, dict):
                item[key] = {"M": cls.convert_to_dynamodb(value)}
            elif isinstance(value, str):
                item[key] = {"S": value}
            elif isinstance(value, int):
                item[key] = {"N": value}
            elif isinstance(value, bool):
                item[key] = {"BOOL", value}
            elif value is None:
                item[key] = {"NULL": value}
        return item

    @classmethod
    def convert_from_dynamodb(cls, item: dict) -> dict:
        obj = {}

        for key, value in item.items():
            if "S" in value:
                obj[key] = value["S"]
            elif "N" in value:
                obj[key] = value["N"]
            elif "BOOL" in value:
                obj[key] = value["BOOL"]
            elif "NULL" in value:
                obj[key] = value["NULL"]
            elif "M" in value:
                obj[key] = cls.convert_from_dynamodb(value["M"])
        return obj
