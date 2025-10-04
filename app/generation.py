from __future__ import annotations

import os
from threading import Lock
from typing import Iterable

try:  # pragma: no cover - transformers is optional
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
except ImportError:  # pragma: no cover - transformers is optional
    AutoModelForCausalLM = None
    AutoTokenizer = None
    pipeline = None

from .models import Message

_model_lock = Lock()
_generation_pipeline = None


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


def generate_response(messages: Iterable[Message]) -> str:
    """Generate a response for the supplied conversation history."""
    prompt = build_prompt(messages)
    try:
        with _model_lock:
            generator = load_generation_pipeline()
            outputs = generator(prompt)
        if outputs and "generated_text" in outputs[0]:
            return outputs[0]["generated_text"].strip() or "(The model returned an empty response.)"
        if outputs and "summary_text" in outputs[0]:
            return outputs[0]["summary_text"].strip() or "(The model returned an empty response.)"
        return "(No response generated.)"
    except RuntimeError:
        return (
            "[Model not loaded] Configure the MODEL_NAME environment variable and install "
            "transformers to enable text generation."
        )
    except Exception as exc:  # pragma: no cover - logging placeholder
        return f"An error occurred while generating a response: {exc}"
