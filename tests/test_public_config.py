import os
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


@pytest.mark.parametrize('bom', [b'\xef\xbb\xbf', b''])
def test_env_file_is_read_with_or_without_bom(tmp_path, monkeypatch, bom):
    from app.config import load_env_file
    env = tmp_path / '.env'
    env.write_bytes(bom + 'FINSIM_BOM_TEST_KEY=placeholder\nFINSIM_BOM_TEST_OTHER=二\n'.encode('utf-8'))
    for name in ('FINSIM_BOM_TEST_KEY', 'FINSIM_BOM_TEST_OTHER'):
        # setenv registers the original state so the variable is removed after the test.
        monkeypatch.setenv(name, '')
        monkeypatch.delenv(name)
    assert load_env_file(env)
    assert os.environ['FINSIM_BOM_TEST_KEY'] == 'placeholder'
    assert os.environ['FINSIM_BOM_TEST_OTHER'] == '二'
