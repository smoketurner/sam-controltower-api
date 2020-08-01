#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json


def build_response(code: int, data: dict = None, headers: dict = None) -> dict:

    response = {"statusCode": code, "headers": {}}

    if headers and isinstance(headers, dict):
        response["headers"].update(headers)

    response["headers"]["Cache-Control"] = "no-cache,no-store,must-revalidate,max-age=0"
    response["headers"]["Expires"] = "0"
    response["headers"]["Pragma"] = "no-cache"

    if data is not None:
        response["headers"]["Content-Type"] = "application/json; charset=utf-8"
        response["body"] = json.dumps(
            data, sort_keys=True, indent=None, separators=(",", ":")
        )

    return response


def error_response(code: int, message: str) -> dict:
    return build_response(code, {"code": code, "message": message})
