from html.parser import HTMLParser
from urllib.parse import urljoin

from fastapi.testclient import TestClient

from main import app


class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.assets = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a':
            self.links.append(attrs.get('href', ''))
        if tag == 'script' and 'src' in attrs:
            self.assets.append(attrs['src'])
        if tag == 'link' and attrs.get('rel') == 'stylesheet':
            self.assets.append(attrs['href'])


def test_questionnaire_entry_and_all_assets_are_served_by_existing_app():
    with TestClient(app) as client:
        workspace = client.get('/vehicle.html')
        entry = PageLinks()
        entry.feed(workspace.text)
        assert '/car-needs.html' in entry.links

        page = client.get('/car-needs.html')
        assert page.status_code == 200
        assert 'FinSim | 個人化選車問卷' in page.text
        parser = PageLinks()
        parser.feed(page.text)
        assert len(parser.assets) == 5
        for asset in parser.assets:
            response = client.get(urljoin('/car-needs.html', asset))
            assert response.status_code == 200, asset
            assert not response.text.startswith('<!doctype'), asset
        assert '/vehicle.html' in parser.links


def test_questionnaire_catalog_dependency_and_original_entrypoints_remain_available():
    with TestClient(app) as client:
        catalog = client.get('/decisions/vehicle/catalog')
        assert catalog.status_code == 200
        vehicles = catalog.json()
        assert isinstance(vehicles, list) and vehicles
        assert all({'id', 'brand', 'model', 'trim', 'price_twd'} <= vehicle.keys()
                   for vehicle in vehicles)
        root = client.get('/', follow_redirects=False)
        assert root.headers['location'] == '/vehicle.html'
        assert client.get('/decisions/vehicle/assumptions').status_code == 200
