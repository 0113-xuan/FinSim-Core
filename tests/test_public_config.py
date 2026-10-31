from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

import main


@pytest.mark.parametrize('url,public_value,configured', [
    ('https://example.supabase.co', 'public-test-placeholder', True),
    ('', '', False),
    ('https://example.supabase.co', '', False),
    ('', 'public-test-placeholder', False),
])
def test_public_config_only_returns_public_fields(monkeypatch, url, public_value, configured):
    monkeypatch.setattr(main, 'settings', replace(main.settings, supabase_url=url, supabase_key=public_value))
    response = TestClient(main.app).get('/config/public')
    assert response.status_code == 200
    assert response.json() == {
        'supabase_url': url if configured else '',
        'supabase_anon_key': public_value if configured else '',
        'configured': configured,
    }
    assert response.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('method,path', [
    ('POST', '/auth/register'), ('POST', '/auth/login'),
    ('GET', '/financial-profile'), ('POST', '/financial-profile'),
])
def test_in_memory_auth_routes_are_removed(method, path):
    # The root StaticFiles mount returns 405 for POST requests to absent routes.
    assert TestClient(main.app).request(method, path, json={}).status_code in {404, 405}
    assert path not in main.app.openapi()['paths']
