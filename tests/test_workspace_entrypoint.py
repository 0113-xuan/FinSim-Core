from fastapi.testclient import TestClient
from main import app


def test_home_opens_vehicle_workspace():
    client=TestClient(app)
    response=client.get('/',follow_redirects=False)
    assert response.status_code==302
    assert response.headers['location']=='/vehicle.html'
    assert response.headers['cache-control']=='no-store'
    page=client.get('/')
    assert page.status_code==200
    assert page.url.path=='/vehicle.html'
    assert 'FinSim | 購車決策' in page.text
    assert '舊版工作區' not in page.text


def test_head_redirects_and_existing_routes_remain_available():
    client=TestClient(app)
    assert client.head('/',follow_redirects=False).headers['location']=='/vehicle.html'
    assert client.get('/decisions/vehicle/catalog').status_code==200
    assert client.get('/index.html').status_code==200
