#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime
import json
import os
from typing import Dict, Any
import secrets

from .controltowerapi.secretsmanager import SecretsManager


SECRET_ID = os.environ["SECRET_ID"]
TOKEN = None

__all__ = ["build_response", "error_response", "authenticate_request"]


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj) -> str:
        if isinstance(obj, datetime):
            return obj.isoformat() + "Z"
        return super().default(obj)


def build_response(
    code: int, data: Dict[str, Any] = None, headers: Dict[str, str] = None
) -> Dict[str, Any]:

    response = {"statusCode": code, "headers": {}}

    if headers and isinstance(headers, dict):
        response["headers"].update(headers)

    response["headers"]["Cache-Control"] = "no-cache,no-store,must-revalidate,max-age=0"
    response["headers"]["Expires"] = "0"
    response["headers"]["Pragma"] = "no-cache"

    if data is not None:
        response["headers"]["Content-Type"] = "application/json; charset=utf-8"
        response["body"] = json.dumps(
            data,
            sort_keys=True,
            indent=None,
            separators=(",", ":"),
            default=DateTimeEncoder,
        )

    return response


def error_response(code: int, message: str) -> Dict[str, Any]:
    return build_response(code, {"code": code, "message": message})


def authenticate_request(event) -> bool:
    """
    Authenticate the request by validating the Authorization header
    contains the appropriate access token
    """
    authorization = event.get("headers", {}).get("authorization")
    if not authorization:
        return error_response(400, "Authorization header not found")
    elif not authorization.startswith("Bearer "):
        return error_response(
            400, "Authorization header does appear to be a bearer token"
        )

    global TOKEN
    if not TOKEN:
        TOKEN = SecretsManager().get_secret_value(SECRET_ID)

    try:
        access_token = authorization.split(" ")[1]
    except IndexError:
        return error_response(
            400, "Authorization header does appear to be a bearer token"
        )

    if not secrets.compare_digest(TOKEN, access_token):
        return error_response(401, "Unauthorized")

    return True
