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
