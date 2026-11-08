"""
Official Google Gen AI Python SDK integration for Gemini (Phase 7).
Manages secure authentication, streaming and non-streaming generation,
timeouts, controlled retries, and explicit zero-cost error classification.
"""

import asyncio
import logging
from typing import AsyncIterator, Optional, Dict, Any, List

from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError

from backend.app.config import settings

logger = logging.getLogger(__name__)


class GeminiError(Exception):
    """Base exception for RepoMind Gemini client errors."""
    pass


class GeminiConfigError(GeminiError):
    """Raised when GEMINI_API_KEY is missing or invalid."""
    pass


class GeminiQuotaExceededError(GeminiError):
    """Raised when free-tier Google AI Studio quota or rate limits are reached."""
    pass


class GeminiInvalidCredentialsError(GeminiError):
    """Raised when API credentials are rejected."""
    pass


class GeminiModelUnavailableError(GeminiError):
    """Raised when the configured model cannot be accessed."""
    pass


class GeminiSafetyBlockedError(GeminiError):
    """Raised when content is blocked by safety filters."""
    pass


class GeminiTimeoutError(GeminiError):
    """Raised when generation times out."""
    pass


class GeminiClient:
    """
    Client for interacting with Google Gemini models via the official google-genai SDK.
    Supports streaming generation, anti-hallucination configuration, and error categorization.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        client_instance: Optional[Any] = None,
    ):
        self._api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL
        self._custom_client = client_instance
        self._cached_client: Optional[genai.Client] = None

    def _get_client(self) -> genai.Client:
        """Returns or lazily initializes the official Google Gen AI client."""
        if self._custom_client:
            return self._custom_client

        if not self._api_key:
            raise GeminiConfigError(
                "GEMINI_API_KEY is not configured. Please set GEMINI_API_KEY in your .env file "
                "or obtain a free API key at https://aistudio.google.com/."
            )

        if not self._cached_client:
            self._cached_client = genai.Client(api_key=self._api_key)

        return self._cached_client

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
    ) -> str:
        """
        Executes a complete non-streaming answer generation.
        """
        client = self._get_client()
        cfg = types.GenerateContentConfig(
            temperature=temperature if temperature is not None else settings.GEMINI_TEMPERATURE,
            max_output_tokens=max_output_tokens or settings.GEMINI_MAX_OUTPUT_TOKENS,
            system_instruction=system_instruction,
        )

        timeout = timeout_seconds or settings.GEMINI_TIMEOUT_SECONDS

        for attempt in range(2):  # Max 1 retry for transient network glitches
            try:
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                        config=cfg,
                    ),
                    timeout=timeout,
                )

                if not response.text:
                    if hasattr(response, "candidates") and response.candidates:
                        first = response.candidates[0]
                        if hasattr(first, "finish_reason") and "SAFETY" in str(first.finish_reason):
                            raise GeminiSafetyBlockedError("Response was blocked by Gemini safety guidelines.")
                    return "The model returned an empty response. Please try rephrasing your question."

                return response.text

            except asyncio.TimeoutError:
                if attempt == 0:
                    logger.warning(f"Gemini generation timed out after {timeout}s. Retrying once...")
                    await asyncio.sleep(1.0)
                    continue
                raise GeminiTimeoutError(f"Gemini API request timed out after {timeout} seconds.")

            except GeminiError:
                raise
            except APIError as e:
                self._handle_api_error(e)
            except Exception as e:
                logger.exception("Unexpected error in Gemini generate: %s", e)
                raise GeminiError(f"Unexpected generation failure: {str(e)}")

        raise GeminiError("Failed to generate response after retries.")

    async def generate_stream(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """
        Streams answer tokens asynchronously as they are produced by Google Gemini.
        Yields text token chunks.
        """
        client = self._get_client()
        cfg = types.GenerateContentConfig(
            temperature=temperature if temperature is not None else settings.GEMINI_TEMPERATURE,
            max_output_tokens=max_output_tokens or settings.GEMINI_MAX_OUTPUT_TOKENS,
            system_instruction=system_instruction,
        )

        timeout = timeout_seconds or settings.GEMINI_TIMEOUT_SECONDS

        try:
            stream = await asyncio.wait_for(
                client.aio.models.generate_content_stream(
                    model=self.model_name,
                    contents=prompt,
                    config=cfg,
                ),
                timeout=timeout,
            )

            async for chunk in stream:
                if chunk.text:
                    yield chunk.text

        except asyncio.TimeoutError:
            raise GeminiTimeoutError(f"Gemini streaming timed out after {timeout} seconds.")
        except GeminiError:
            raise
        except APIError as e:
            self._handle_api_error(e)
        except Exception as e:
            logger.exception("Unexpected error in Gemini streaming: %s", e)
            raise GeminiError(f"Streaming error: {str(e)}")

    def _handle_api_error(self, e: APIError) -> None:
        """Classifies API errors into user-friendly zero-cost-first messages."""
        msg = str(e)
        code = getattr(e, "code", None)

        if code == 429 or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            logger.warning("Gemini free-tier quota exceeded: %s", msg)
            raise GeminiQuotaExceededError(
                "Google Gemini free-tier quota exceeded. Google AI Studio rate limits require waiting a short period "
                "before making additional requests. Please try again in 30 seconds."
            )
        elif code in (401, 403) or "API_KEY_INVALID" in msg or "permission" in msg.lower():
            logger.error("Gemini credentials rejected: %s", msg)
            raise GeminiInvalidCredentialsError(
                "Invalid GEMINI_API_KEY. Please verify your Google AI Studio API key in the .env file."
            )
        elif code == 404 or "not found" in msg.lower():
            logger.error(f"Gemini model {self.model_name} unavailable: {msg}")
            raise GeminiModelUnavailableError(
                f"Model '{self.model_name}' was not found. Please check GEMINI_MODEL in your .env settings."
            )
        else:
            logger.error(f"Gemini API error (code {code}): {msg}")
            raise GeminiError(f"Gemini API error ({code}): {msg}")


# Global singleton instance
gemini_client = GeminiClient()
