"""Planner adapter with Traditional Chinese request validation errors."""
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.planner_schemas import PlannerVehicleRequest
from app.request_validation import FiniteJSONRoute
from app.services.planner_vehicle import convert_vehicle_events
from app.vehicle_fees import annual_vehicle_tax, insurance_reference
from app.parking import load_regions, load_parking_snapshot, parking_reference


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


@router.get('/regions')
def regions():
    return load_regions()


@router.get('/planner/parking')
def planner_parking(city: str = Query(min_length=1, max_length=10),
                    district: str = Query(min_length=1, max_length=10),
                    snapshot: dict = Depends(load_parking_snapshot)):
    return parking_reference(city, district, snapshot)


@router.get('/planner/vehicle-fees')
def planner_vehicle_fees(displacement_cc: int = Query(ge=0, le=100_000),
                         fuel_type: Literal['gasoline','hybrid','diesel','ev'] = Query(),
                         purchase_price: float = Query(gt=0, le=20_000_000, allow_inf_nan=False)):
    try:
        return dict(tax=annual_vehicle_tax(displacement_cc, fuel_type),insurance=insurance_reference(purchase_price))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.post('/planner/vehicle-events')
def planner_vehicle_events(request: PlannerVehicleRequest):
    try:
        return convert_vehicle_events(request)
    except ValueError:
        raise HTTPException(status_code=422, detail='購車資料無法換算，請確認金額與貸款條件') from None
