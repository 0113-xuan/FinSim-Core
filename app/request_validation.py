"""Reject non-standard JSON numbers before validation or business logic."""
import math
from json import JSONDecodeError

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute


def has_nonfinite_number(value):
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, float) and not math.isfinite(item):
            return True
        if isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return False


def invalid_json_response():
    return JSONResponse(status_code=422, content={'detail': [dict(
        type='json_invalid', loc=['body'], msg='請提供合法 JSON；數值必須為有限值。')]})


class FiniteJSONRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def validate_json(request: Request):
            media_type = request.headers.get('content-type', '').split(';', 1)[0].strip().lower()
            if not media_type or media_type == 'application/json' or media_type.endswith('+json'):
                try:
                    body = await request.body()
                    # Cache parsing on this same Request; the FastAPI handler reuses it.
                    if body and has_nonfinite_number(await request.json()):
                        return invalid_json_response()
                except (JSONDecodeError, UnicodeDecodeError, ValueError, RecursionError):
                    return invalid_json_response()
            return await handler(request)

        return validate_json


async def safe_validation_error(request: Request, exc: RequestValidationError):
    # input and ctx can contain non-JSON values, exceptions, or private financial data.
    errors = [dict(type=error['type'], loc=list(error['loc']), msg=error['msg'])
              for error in exc.errors()]
    return JSONResponse(status_code=422, content={'detail': errors})
