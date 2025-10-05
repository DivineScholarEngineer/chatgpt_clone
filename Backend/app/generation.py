from __future__ import annotations

import logging
import os
import re
import textwrap
from threading import Lock
from typing import Iterable, List, Optional

try:  # pragma: no cover - transformers is optional
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
except ImportError:  # pragma: no cover - transformers is optional
    AutoModelForCausalLM = None
    AutoTokenizer = None
    pipeline = None

from .inference import get_text_client
from .models import Message

_model_lock = Lock()
_generation_pipeline = None
_logger = logging.getLogger(__name__)


def _generate_via_inference(prompt: str) -> Optional[str]:
    """Use the Hugging Face Inference API when it's configured."""

    client = get_text_client()
    if client is None:
        return None

    try:
        max_new_tokens = int(os.getenv("MAX_NEW_TOKENS", "512"))
        temperature = float(os.getenv("TEMPERATURE", "0.7"))
        top_p = float(os.getenv("TOP_P", "0.9"))
    except ValueError:
        max_new_tokens = 512
        temperature = 0.7
        top_p = 0.9

    try:
        response = client.text_generation(
            prompt,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            do_sample=True,
        )
    except Exception as exc:  # pragma: no cover - depends on network
        _logger.warning("Remote text generation failed: %s", exc)
        return None

    if isinstance(response, str):
        return response.strip()

    if isinstance(response, dict):
        text = response.get("generated_text") or response.get("summary_text")
        if text:
            return str(text).strip()

    if isinstance(response, list) and response:
        first = response[0]
        if isinstance(first, dict):
            text = first.get("generated_text") or first.get("summary_text")
            if text:
                return str(text).strip()

    return None


def load_generation_pipeline():
    """Lazy-load the Hugging Face generation pipeline."""
    global _generation_pipeline
    if _generation_pipeline is None:
        if AutoTokenizer is None or AutoModelForCausalLM is None or pipeline is None:
            raise RuntimeError(
                "transformers must be installed to run generation. "
                "Install with `pip install transformers accelerate bitsandbytes`."
            )
        model_name = os.getenv("MODEL_NAME", "openai/gpt-oss-20b")
        quantization = os.getenv("LOAD_IN_4BIT", "true").lower() == "true"
        tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
        model_kwargs = {"device_map": "auto"}
        if quantization:
            model_kwargs["load_in_4bit"] = True
        model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)
        _generation_pipeline = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=int(os.getenv("MAX_NEW_TOKENS", "512")),
            temperature=float(os.getenv("TEMPERATURE", "0.7")),
            top_p=float(os.getenv("TOP_P", "0.9")),
            do_sample=True,
            return_full_text=False,
        )
    return _generation_pipeline


def build_prompt(messages: Iterable[Message]) -> str:
    parts: list[str] = []
    for message in messages:
        role = "User" if message.role == "user" else "Assistant"
        parts.append(f"{role}: {message.content}")
    parts.append("Assistant:")
    return "\n".join(parts)


def _fallback_response(messages: List[Message]) -> str:
    """Return a lightweight response when the model is unavailable."""

    last_user_message = next(
        (
            message.content.strip()
            for message in reversed(messages)
            if message.role == "user" and message.content.strip()
        ),
        "",
    )

    if not last_user_message:
        return (
            "I'm here and ready whenever you are. The full model is still warming up, "
            "so feel free to ask a question in the meantime.\n\n"
            "(Model temporarily unavailable; provided a backup response.)"
        )

    normalized = re.sub(r"\s+", " ", last_user_message)
    summary = textwrap.shorten(normalized, width=160, placeholder="…")

    tokens = [
        re.sub(r"[^a-z0-9]", "", word.lower())
        for word in normalized.split()
        if len(word) > 3
    ]
    seen: list[str] = []
    for token in tokens:
        if token not in seen:
            seen.append(token)
        if len(seen) == 3:
            break

    if seen:
        keyword_lines = "\n".join(f"- {word.title()}" for word in seen)
    else:
        keyword_lines = "- I'm ready to dig in whenever you are."

    return (
        "I'm operating in a lightweight mode right now, so here's a quick reflection "
        "instead of a full model reply.\n\n"
        f"Summary: {summary}\n"
        "Key ideas I'm noticing:\n"
        f"{keyword_lines}\n\n"
        "Let me know if you'd like to explore any of those in more detail.\n\n"
        "(Model temporarily unavailable; provided a backup response.)"
    )


def generate_response(messages: Iterable[Message]) -> str:
    """Generate a response for the supplied conversation history."""
    history = list(messages)
    prompt = build_prompt(history)

    remote_reply = _generate_via_inference(prompt)
    if remote_reply:
        return remote_reply

    try:
        with _model_lock:
            generator = load_generation_pipeline()
            outputs = generator(prompt)
        if outputs and "generated_text" in outputs[0]:
            return outputs[0]["generated_text"].strip() or "(The model returned an empty response.)"
        if outputs and "summary_text" in outputs[0]:
            return outputs[0]["summary_text"].strip() or "(The model returned an empty response.)"
        return "(No response generated.)"
    except RuntimeError as exc:
        _logger.warning("Generation pipeline unavailable; using fallback: %s", exc)
        return _fallback_response(history)
    except Exception as exc:  # pragma: no cover - logging placeholder
        _logger.exception("Generation pipeline failed", exc_info=exc)
        return _fallback_response(history)
