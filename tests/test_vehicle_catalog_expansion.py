from collections import Counter
from datetime import date

from fastapi.testclient import TestClient

from app.vehicle_catalog import catalog_list, get_vehicle
from app.recommendation_catalog import recommendation_catalog
from main import app
from tests.test_vehicle_decision import request_data
from tests.test_planner_vehicle import PROFILE, request


CLIENT = TestClient(app)
LEGACY_IDS = {'toyota-cross-gas-luxury', 'toyota-cross-hybrid-luxury',
              'toyota-cross-hybrid-flagship', 'honda-hrv-hybrid-s',
              'honda-hrv-hybrid-prestige'}


def test_complete_catalog_has_sourced_specs_and_preserves_legacy_ids():
    cars = catalog_list(include_ev=True)
    assert len(cars) >= 30
    assert len({car['id'] for car in cars}) == len(cars)
    assert LEGACY_IDS <= {car['id'] for car in cars}
    assert sum(car['fuel_type'] == 'ev' for car in cars) >= 3
    assert sum(car['brand'] in {'Lexus', 'BMW', 'Mercedes-Benz', 'Volvo'} for car in cars) >= 3
    counts = Counter((car['brand'], car['model']) for car in cars)
    assert all(count <= 2 for key, count in counts.items() if key != ('Toyota', 'Corolla Cross'))
    for car in cars:
        assert get_vehicle(car['id']) == car
        assert type(car['price_twd']) is int and car['price_twd'] > 0
        assert car['source_url'].startswith('https://') and car['spec_source'].startswith('https://')
        assert date.fromisoformat(car['checked_on'])
        assert car['fuel_type'] in {'gasoline', 'hybrid', 'diesel', 'ev'}
        if car['fuel_type'] == 'ev':
            assert car['displacement_cc'] == 0 and car['efficiency_km_l'] is None
        else:
            assert car['displacement_cc'] > 0 and car['efficiency_km_l'] > 0
    recommendations = {car['id']: car for car in recommendation_catalog()}
    for planner_id, recommendation_id in [('toyota-altis-classic', 'altis-classic'),
                                          ('honda-fit-home', 'fit-home'), ('honda-fit-hybrid', 'fit-hev')]:
        assert get_vehicle(planner_id)['price_twd'] == recommendations[recommendation_id]['price_twd']


def test_catalog_api_ev_opt_in_and_preset_rejection():
    default = CLIENT.get('/decisions/vehicle/catalog')
    complete = CLIENT.get('/decisions/vehicle/catalog?include_ev=true')
    assert default.status_code == complete.status_code == 200
    assert default.json() == [car for car in complete.json() if car['efficiency_km_l'] is not None]
    evs = [car for car in complete.json() if car['fuel_type'] == 'ev']
    assert evs
    for car in evs:
        response = CLIENT.post('/decisions/vehicle/preset', json=dict(
            vehicle_id=car['id'], annual_distance_km=15000, fuel_price_twd_l=30))
        assert response.status_code == 422
        assert response.json()['detail'] == '電動車沒有官方油耗，請自行填寫每月充電費用。'


def test_ev_catalog_id_is_accepted_by_planner_and_vehicle_analysis_with_zero_tax():
    car = next(car for car in catalog_list(include_ev=True) if car['fuel_type'] == 'ev')
    fees = CLIENT.get('/planner/vehicle-fees', params=dict(
        displacement_cc=car['displacement_cc'], fuel_type=car['fuel_type'], purchase_price=car['price_twd']))
    assert fees.status_code == 200
    tax = fees.json()['tax']
    assert tax['license_tax'] == tax['total'] == 0
    details = dict(vehicle_catalog_id=car['id'], purchase_price=car['price_twd'],
                   payment_method='cash', displacement_cc=0, fuel_type='ev', annual_tax=tax['total'])
    converted = CLIENT.post('/planner/vehicle-events', json=request(details))
    assert converted.status_code == 200, converted.json()
    data = converted.json()
    simulation = CLIENT.post('/simulate', json=dict(profile=PROFILE, months=60,
                                                    events=data['events'], loans=data['loans'],
                                                    assets=data['assets']))
    assert simulation.status_code == 200, simulation.json()
    decision = request_data()
    decision['vehicle_catalog_id'] = car['id']
    decision['scenario']['payload']['purchase_price'] = dict(value=car['price_twd'], source='user_provided')
    decision['scenario']['payload']['annual_tax'] = dict(value=0, source='user_provided')
    result = CLIENT.post('/decisions/vehicle', json=decision)
    assert result.status_code == 200, result.json()
    assert result.json()['selected_vehicle']['id'] == car['id']
