"""Offline configuration probe. Never calls generate_structured or external HTTP."""
import json
import os
from pathlib import Path

from dotenv import dotenv_values

from app.config import settings
from app.services.ai_provider import get_ai_provider
from app.services.prompt_loader import load_prompt


def diagnose():
    env_path = Path(__file__).resolve().parents[1] / '.env'
    file_values = dotenv_values(env_path) if env_path.is_file() else {}
    supported = settings.ai_provider in ('gemini', 'openai')
    key = settings.gemini_api_key if settings.ai_provider == 'gemini' else settings.ai_api_key
    model = settings.gemini_model if settings.ai_provider == 'gemini' else settings.ai_model
    # Do not echo a secret accidentally configured as a model name.
    secrets = [settings.gemini_api_key, settings.ai_api_key, settings.car_needs_signing_key]
    safe_model = model if not any(value and value in model for value in secrets) else None
    signing_valid = not settings.car_needs_signing_key or len(settings.car_needs_signing_key.encode()) >= 32
    result = dict(
        ai_enabled=settings.ai_enabled,
        provider=settings.ai_provider if supported else 'unsupported',
        provider_supported=supported,
        model=safe_model,
        model_configured=bool(model.strip()),
        dotenv_exists=env_path.is_file(),
        dotenv_ai_enabled=(file_values.get('AI_ENABLED') or '').strip().lower() == 'true',
        process_ai_enabled_present='AI_ENABLED' in os.environ,
        provider_key_present=bool(key) if supported else False,
        signing_key_configured=bool(settings.car_needs_signing_key),
        signing_key_valid=signing_valid,
        provider_initialized=False,
        prompt_loaded=False,
        initialization_error_type=None,
        prompt_error_type=None,
        external_http_attempted=False,
    )
    try:
        result['provider_initialized'] = get_ai_provider() is not None
    except Exception as exc:
        result['initialization_error_type'] = type(exc).__name__
    try:
        result['prompt_loaded'] = bool(load_prompt('car_needs_extraction.md'))
    except Exception as exc:
        result['prompt_error_type'] = type(exc).__name__
    if not result['ai_enabled']:
        error = 'ai_disabled'
    elif not supported:
        error = 'unsupported_provider'
    elif not result['provider_key_present']:
        error = 'missing_api_key'
    elif result['initialization_error_type'] or not result['provider_initialized']:
        error = 'provider_initialization_failed'
    elif not result['model_configured']:
        error = 'missing_model'
    elif not result['prompt_loaded']:
        error = 'prompt_unavailable'
    elif not signing_valid:
        error = 'invalid_signing_key'
    else:
        error = None
    result['error_category'] = error
    result['configuration_ready'] = error is None
    return result


if __name__ == '__main__':
    print(json.dumps(diagnose(), ensure_ascii=False, indent=2))
