from fastapi.testclient import TestClient

from main import app


def test_static_files_are_revalidated_so_a_deploy_is_not_hidden_by_the_browser_cache():
    client = TestClient(app)
    first = client.get('/shell.js')
    assert first.status_code == 200
    assert first.headers['cache-control'] == 'no-cache'
    # Revalidation stays cheap: an unchanged file answers 304 to its own ETag.
    second = client.get('/shell.js', headers={'If-None-Match': first.headers['etag']})
    assert second.status_code == 304
