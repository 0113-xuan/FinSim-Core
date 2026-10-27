"""Global malformed JSON must be a serializable 422, never a server exception."""
import asyncio
import json

import pytest
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.request_validation import FiniteJSONRoute, safe_validation_error
from main import app


@pytest.mark.parametrize('token', ['NaN', 'Infinity', '-Infinity', '1e9999', '-1e9999'])
@pytest.mark.parametrize('endpoint', ['/decisions/vehicle/recommendations', '/decisions/vehicle/costs', '/financial-profile'])
def test_nonfinite_raw_json_is_rejected_globally(endpoint, token):
    # Nested arrays also exercise the formerly untyped financial-profile route.
    content = '{"nested": [{"value": ' + token + '}]}'
    response = TestClient(app).post(endpoint, content=content, headers={'content-type': 'application/json'})
    assert response.status_code == 422
    result = response.json()
    assert result['detail'][0]['type'] == 'json_invalid'
    assert set(result['detail'][0]) == {'type', 'loc', 'msg'}
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('content', [b'{', b'{"value":', b'{"value":"\xff"}'])
def test_invalid_json_and_encoding_do_not_escape_handler(content):
    response = TestClient(app).post('/decisions/vehicle/costs', content=content, headers={'content-type': 'application/json'})
    assert response.status_code == 422
    assert response.json()['detail'][0]['type'] == 'json_invalid'


def test_deep_json_is_controlled_without_echoing_nested_input():
    content = b'{"x":' + b'[' * 1200 + b'0' + b']' * 1200 + b'}'
    response = TestClient(app).post('/decisions/vehicle/costs', content=content, headers={'content-type':'application/json'})
    assert response.status_code == 422
    assert all('input' not in e for e in response.json()['detail'])
    json.dumps(response.json(), allow_nan=False)


@pytest.mark.parametrize('media_type', [None, 'application/json; charset=utf-8', 'application/problem+json'])
def test_json_media_types_and_missing_content_type(media_type):
    headers = {'content-type': media_type} if media_type else {}
    response = TestClient(app).post('/decisions/vehicle/costs', content='{"x":NaN}', headers=headers)
    assert response.status_code == 422
    assert response.json()['detail'][0]['type'] == 'json_invalid'


def test_error_handler_omits_nonserializable_context_and_private_input():
    exc = RequestValidationError([dict(type='finite_number', loc=('body', 'value'), msg='數值不合法',
        input=float('nan'), ctx={'error': ValueError('private financial conversation')})])
    response = asyncio.run(safe_validation_error(None, exc))
    assert response.status_code == 422
    assert json.loads(response.body) == {'detail': [dict(type='finite_number', loc=['body', 'value'], msg='數值不合法')]}


def test_invalid_non_json_bytes_are_not_echoed():
    response = TestClient(app).post('/decisions/vehicle/costs', content=b'\xff', headers={'content-type': 'text/plain'})
    assert response.status_code == 422
    assert 'input' not in response.json()['detail'][0]


def test_number_words_inside_strings_are_not_rejected_as_json_constants():
    response = TestClient(app).post('/decisions/vehicle/costs', json={'note': 'NaN Infinity -Infinity'})
    assert response.status_code == 422
    assert all(e['type'] != 'json_invalid' for e in response.json()['detail'])


def test_all_existing_api_routes_use_shared_json_guard():
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    assert routes and all(isinstance(route, FiniteJSONRoute) for route in routes)
