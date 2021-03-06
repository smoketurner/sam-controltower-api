#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Dict, Optional, Any

from aws_lambda_powertools import Logger
import boto3
import botocore

CT_PORTFOLIO_NAME = "AWS Control Tower Account Factory Portfolio"
CT_PRODUCT_NAME = "AWS Control Tower Account Factory"
logger = Logger(child=True)

__all__ = ["ServiceCatalog"]


class ServiceCatalog:
    def __init__(self) -> None:
        self.client = boto3.client("servicecatalog")

    def get_ct_portfolio_id(self) -> Optional[str]:
        """
        Return the portfolio ID for the Control Tower Account Factory Portfolio
        """
        paginator = self.client.get_paginator("list_portfolios")
        page_iterator = paginator.paginate()
        for page in page_iterator:
            for portfolio in page.get("PortfolioDetails", []):
                if portfolio["DisplayName"] == CT_PORTFOLIO_NAME:
                    return portfolio["Id"]
        return None

    def associate_principal(self, portfolio_id: str, principal_arn: str) -> None:
        """
        Associate an IAM principal to a portfolio
        """
        try:
            self.client.associate_principal_with_portfolio(
                PortfolioId=portfolio_id,
                PrincipalARN=principal_arn,
                PrincipalType="IAM",
            )
        except botocore.exceptions.ClientError:
            logger.exception(
                f"Unable to associate principal to portfolio {portfolio_id}"
            )

    def get_ct_product(self) -> Dict[str, str]:
        """
        Get the Control Tower account provision product ID
        """

        product_id = None

        response = self.client.search_products(Filters={"Owner": ["AWS Control Tower"]})
        for product in response.get("ProductViewSummaries", []):
            if product["Name"] == CT_PRODUCT_NAME:
                product_id = product["ProductId"]
                break

        if not product_id:
            raise Exception(f"Unable to locate product '{CT_PRODUCT_NAME}'")

        artifact_id = None

        response = self.client.describe_product(Id=product_id)
        for artifact in response.get("ProvisioningArtifacts", []):
            if artifact.get("Guidance") == "DEFAULT":
                artifact_id = artifact["Id"]
                break

        if not artifact_id:
            raise Exception("Unable to locate active provisioning artifact")

        data = {"ProductId": product_id, "ProvisioningArtifactId": artifact_id}

        logger.debug(data)

        return data

    def provision_product(
        self, product: Dict[str, str], parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Provision a new AWS account
        """

        params = {
            "ProvisionedProductName": parameters["AccountName"],
            "ProvisioningParameters": [
                {"Key": key, "Value": value} for key, value in parameters.items()
            ],
        }

        params.update(product)

        logger.info(params)

        try:
            response = self.client.provision_product(**params)
        except botocore.exceptions.ClientError as error:
            logger.exception("Unable to provision product")
            raise error

        return response.get("RecordDetail", {})

    def describe_record(self, record_id: str) -> Dict[str, Any]:
        """
        Describe a provisioned product record
        """
        try:
            response = self.client.describe_record(Id=record_id)
        except botocore.exceptions.ClientError as error:
            logger.exception("Unable to describe record")
            raise error

        return response
