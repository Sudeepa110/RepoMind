"""
Unit tests for Gemini Client (Phase 7).
Tests official Google Gen AI SDK wrapper, mock response streaming,
anti-prompt injection safeguards, and zero-cost error classification.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from google.genai.errors import APIError

from backend.app.llm.gemini_client import (
    GeminiClient,
    GeminiConfigError,
    GeminiQuotaExceededError,
    GeminiInvalidCredentialsError,
    GeminiModelUnavailableError,
    GeminiSafetyBlockedError,
    GeminiTimeoutError,
    GeminiError,
)


def test_missing_api_key_raises_config_error():
    client = GeminiClient(api_key="")
    with pytest.raises(GeminiConfigError) as exc_info:
        client._get_client()
    assert "GEMINI_API_KEY is not configured" in str(exc_info.value)


@pytest.mark.asyncio
async def test_successful_generate():
    mock_sdk = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Authentication is implemented in `verify_token` [auth.py:10-25]."
    mock_sdk.aio.models.generate_content = AsyncMock(return_value=mock_response)

    client = GeminiClient(api_key="fake-test-key", client_instance=mock_sdk)
    result = await client.generate("Where is auth?")

    assert "Authentication is implemented" in result
    mock_sdk.aio.models.generate_content.assert_called_once()


@pytest.mark.asyncio
async def test_successful_generate_stream():
    mock_sdk = MagicMock()

    class MockChunk:
        def __init__(self, text):
            self.text = text

    async def mock_stream_gen():
        yield MockChunk("Hello ")
        yield MockChunk("world")
        yield MockChunk("!")

    mock_sdk.aio.models.generate_content_stream = AsyncMock(return_value=mock_stream_gen())

    client = GeminiClient(api_key="fake-test-key", client_instance=mock_sdk)
    tokens = []
    async for token in client.generate_stream("Hi"):
        tokens.append(token)

    assert "".join(tokens) == "Hello world!"


@pytest.mark.asyncio
async def test_error_classification_quota():
    mock_sdk = MagicMock()
    err = APIError(429, {"error": {"message": "Resource exhausted: Quota exceeded for model gemini-2.5-flash"}})
    mock_sdk.aio.models.generate_content = AsyncMock(side_effect=err)

    client = GeminiClient(api_key="fake-test-key", client_instance=mock_sdk)
    with pytest.raises(GeminiQuotaExceededError) as exc_info:
        await client.generate("test query")
    assert "Google Gemini free-tier quota exceeded" in str(exc_info.value)


@pytest.mark.asyncio
async def test_error_classification_invalid_credentials():
    mock_sdk = MagicMock()
    err = APIError(403, {"error": {"message": "API_KEY_INVALID: The provided API key is expired or invalid"}})
    mock_sdk.aio.models.generate_content = AsyncMock(side_effect=err)

    client = GeminiClient(api_key="fake-test-key", client_instance=mock_sdk)
    with pytest.raises(GeminiInvalidCredentialsError) as exc_info:
        await client.generate("test query")
    assert "Invalid GEMINI_API_KEY" in str(exc_info.value)


@pytest.mark.asyncio
async def test_error_classification_model_not_found():
    mock_sdk = MagicMock()
    err = APIError(404, {"error": {"message": "Model not found: models/gemini-2.5-flash"}})
    mock_sdk.aio.models.generate_content = AsyncMock(side_effect=err)

    client = GeminiClient(api_key="fake-test-key", client_instance=mock_sdk)
    with pytest.raises(GeminiModelUnavailableError) as exc_info:
        await client.generate("test query")
    assert "was not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_safety_blocked_handling():
    mock_sdk = MagicMock()
    mock_candidate = MagicMock()
    mock_candidate.finish_reason = "SAFETY"
    mock_response = MagicMock()
    mock_response.text = None
    mock_response.candidates = [mock_candidate]
    mock_sdk.aio.models.generate_content = AsyncMock(return_value=mock_response)

    client = GeminiClient(api_key="fake-test-key", client_instance=mock_sdk)
    with pytest.raises(GeminiSafetyBlockedError) as exc_info:
        await client.generate("test query")
    assert "safety guidelines" in str(exc_info.value)
