import pytest
from fastapi.testclient import TestClient
from main import app
from app.vehicle_catalog import VehiclePresetRequest, vehicle_preset, catalog_list
from app.decision_schemas import VehicleDecisionRequest
from tests.test_vehicle_decision import request_data


def test_catalog_sources_and_currency():
    client = TestClient(app)
    response = client.get('/decisions/vehicle/catalog')
    assert response.status_code == 200
    items = response.json()
    assert len({item['id'] for item in items}) == len(items) == 5
    assert all(item['currency'] == 'TWD' and item['source_url'].startswith('https://') and item['source_period'] for item in items)


@pytest.mark.parametrize('distance,fuel', [(15000,30), (0,30), (15000,0)])
def test_fuel_preset_formula(distance, fuel):
    vehicle = catalog_list()[0]
    result = vehicle_preset(VehiclePresetRequest(vehicle_id=vehicle['id'], annual_distance_km=distance, fuel_price_twd_l=fuel))
    assert result['purchase_price'] == 809000
    assert result['monthly_fuel_or_energy'] == pytest.approx(distance / 14.3 * fuel / 12, abs=.005)
    assert 'annual_insurance' not in result


def test_preset_validation_and_legacy_request():
    client = TestClient(app)
    body = dict(vehicle_id='unknown', annual_distance_km=15000, fuel_price_twd_l=30)
    assert client.post('/decisions/vehicle/preset', json=body).status_code == 422
    body['vehicle_id'] = catalog_list()[0]['id']
    for key, value in [('annual_distance_km', -1), ('fuel_price_twd_l', 'NaN'), ('extra', True)]:
        assert client.post('/decisions/vehicle/preset', json={**body, key:value}).status_code == 422
    data = request_data()
    assert VehicleDecisionRequest.model_validate(data).vehicle_catalog_id is None
    data['vehicle_catalog_id'] = body['vehicle_id']
    assert VehicleDecisionRequest.model_validate(data).vehicle_catalog_id == body['vehicle_id']
    data['vehicle_catalog_id'] = 'unknown'
    with pytest.raises(ValueError):
        VehicleDecisionRequest.model_validate(data)
