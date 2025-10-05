"""Helpers for accessing remote Hugging Face inference endpoints."""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Optional

try:  # pragma: no cover - optional dependency
    from huggingface_hub import InferenceClient
except ImportError:  # pragma: no cover - optional dependency
    InferenceClient = None  # type: ignore[assignment]

_logger = logging.getLogger(__name__)


def _resolve_model_name(preferred: str | None, fallback: str | None) -> Optional[str]:
    if preferred and preferred.strip():
        return preferred.strip()
    if fallback and fallback.strip():
        return fallback.strip()
    return None


@lru_cache(maxsize=1)
def get_text_client() -> Optional["InferenceClient"]:
    """Return a cached Hugging Face inference client for text generation."""

    if InferenceClient is None:
        return None

    model = _resolve_model_name(os.getenv("HF_TEXT_MODEL"), os.getenv("MODEL_NAME"))
    endpoint = os.getenv("HF_TEXT_ENDPOINT") or os.getenv("HF_INFERENCE_ENDPOINT")
    token = os.getenv("HF_API_TOKEN")

    if not (model or endpoint):
        return None

    try:
        return InferenceClient(model=endpoint or model or "", token=token or None)
    except Exception as exc:  # pragma: no cover - depends on network
        _logger.warning("Failed to initialise Hugging Face text client: %s", exc)
        return None


@lru_cache(maxsize=1)
def get_image_client() -> Optional["InferenceClient"]:
    """Return a cached Hugging Face inference client for text-to-image."""

    if InferenceClient is None:
        return None

    model = _resolve_model_name(os.getenv("HF_IMAGE_MODEL"), os.getenv("IMAGE_MODEL"))
    endpoint = os.getenv("HF_IMAGE_ENDPOINT")
    token = os.getenv("HF_API_TOKEN")

    if not (model or endpoint):
        return None

    try:
        return InferenceClient(model=endpoint or model or "", token=token or None)
    except Exception as exc:  # pragma: no cover - depends on network
        _logger.warning("Failed to initialise Hugging Face image client: %s", exc)
        return None
