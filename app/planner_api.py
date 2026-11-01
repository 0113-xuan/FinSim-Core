"""Planner adapter with Traditional Chinese request validation errors."""
import re

from fastapi import APIRouter, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.planner_schemas import PlannerVehicleRequest
from app.request_validation import FiniteJSONRoute
from app.services.planner_vehicle import convert_vehicle_events


class PlannerRoute(FiniteJSONRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def localized(request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                errors = []
                for error in exc.errors():
                    message = error['msg'].removeprefix('Value error, ')
                    if not re.search(r'[\u4e00-\u9fff]', message):
                        message = ('請填寫必要欄位' if error['type'] == 'missing'
                                   else '欄位格式或數值不正確，請確認付款方式、金額、月份與期數')
                    errors.append(dict(loc=list(error['loc']), msg=message, type=error['type']))
                return JSONResponse(status_code=422, content={'detail': errors})
        return localized


router = APIRouter(route_class=PlannerRoute)


@router.post('/planner/vehicle-events')
def planner_vehicle_events(request: PlannerVehicleRequest):
    try:
        return convert_vehicle_events(request)
    except ValueError:
        raise HTTPException(status_code=422, detail='購車資料無法換算，請確認金額與貸款條件') from None
