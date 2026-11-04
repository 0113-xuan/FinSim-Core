import pytest
from fastapi.testclient import TestClient
from main import app
from app.vehicle_catalog import VehiclePresetRequest, vehicle_preset, catalog_list, get_vehicle
from app.recommendation_catalog import recommendation_catalog
from datetime import date
from app.decision_schemas import VehicleDecisionRequest
from tests.test_vehicle_decision import request_data


def test_catalog_sources_and_currency():
    client = TestClient(app)
    response = client.get('/decisions/vehicle/catalog')
    assert response.status_code == 200
    items = response.json()
    assert len({item['id'] for item in items}) == len(items) == len(catalog_list())
    assert all(item['currency'] == 'TWD' and item['source_url'].startswith('https://') and item['source_period'] for item in items)


def test_vehicle_records_own_their_specs_and_verification_dates():
    for item in catalog_list():
        assert get_vehicle(item['id']) == item
        assert date.fromisoformat(item['checked_on'])
        assert item['displacement_cc'] > 0
        assert item['spec_source'].startswith('https://')
    recommended = {item['id']: item for item in recommendation_catalog()}
    for vehicle_id, recommendation_id in [
        ('toyota-cross-gas-luxury', 'cc-gas-luxury'),
        ('toyota-cross-hybrid-luxury', 'cc-hev-luxury'),
        ('toyota-cross-hybrid-flagship', 'cc-hev-flagship'),
    ]:
        assert get_vehicle(vehicle_id)['price_twd'] == recommended[recommendation_id]['price_twd']
    # A blocked ordering page must not inherit a new verification date.
    assert recommended['model3-lr-rwd']['checked_on'] == '2026-10-26'
    assert recommended['model3-lr-rwd']['verification']['price'] == 'indexed_only'


@pytest.mark.parametrize('distance,fuel', [(15000,30), (0,30), (15000,0)])
def test_fuel_preset_formula(distance, fuel):
    vehicle = catalog_list()[0]
    result = vehicle_preset(VehiclePresetRequest(vehicle_id=vehicle['id'], annual_distance_km=distance, fuel_price_twd_l=fuel))
    assert result['purchase_price'] == vehicle['price_twd']
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
