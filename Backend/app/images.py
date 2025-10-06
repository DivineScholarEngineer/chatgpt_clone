"""Text-to-image helpers with graceful fallbacks."""
from __future__ import annotations

import io
import logging
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Tuple

from django.conf import settings
from django.utils import timezone
from posixpath import join as url_path_join

try:  # pragma: no cover - optional dependencies
    from PIL import Image
except ImportError:  # pragma: no cover - optional dependencies
    Image = None  # type: ignore[assignment]

from .generation import remote_text
from .imageforge import forge_images
from .inference import get_image_client

_logger = logging.getLogger(__name__)


@dataclass
class GeneratedImage:
    identifier: str
    prompt: str
    relative_path: str
    mime_type: str
    palette: List[str]
    created_at: datetime
    provider: str
    caption: str
    director_prompt: str

    @property
    def filename(self) -> str:
        return Path(self.relative_path).name

    @property
    def url(self) -> str:
        base = str(settings.MEDIA_URL).rstrip("/") or "/"
        return url_path_join(base, self.relative_path)


def _media_dir() -> Path:
    target = Path(settings.MEDIA_ROOT) / "imageforge"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _extract_palette(image: "Image.Image") -> List[str]:  # pragma: no cover - visuals
    palette: List[str] = []
    try:
        reduced = image.convert("P", palette=Image.ADAPTIVE, colors=4).convert("RGB")
        colors = reduced.getcolors(1024) or []
        colors.sort(key=lambda item: item[0], reverse=True)
        for _, rgb in colors[:3]:
            palette.append("#%02x%02x%02x" % rgb)
    except Exception as exc:  # pragma: no cover - best effort only
        _logger.debug("Unable to derive palette: %s", exc)
    if not palette:
        palette = ["#334155", "#6366f1", "#f472b6"]
    return palette


def _generate_via_huggingface(
    director_prompt: str, count: int, caption: str, original_prompt: str
) -> Iterable[GeneratedImage]:
    client = get_image_client()
    if client is None or Image is None:
        return []

    width = int(os.getenv("IMAGE_WIDTH", "768"))
    height = int(os.getenv("IMAGE_HEIGHT", "768"))
    guidance = float(os.getenv("IMAGE_GUIDANCE_SCALE", "3.5"))
    steps = int(os.getenv("IMAGE_INFERENCE_STEPS", "8"))

    output_dir = _media_dir()
    timestamp = timezone.now()
    results: List[GeneratedImage] = []

    for index in range(count):
        seed = secrets.token_hex(8)
        try:
            pil_image = client.text_to_image(
                f"{director_prompt}, variation {index + 1}",
                width=width,
                height=height,
                guidance_scale=guidance,
                num_inference_steps=steps,
            )
        except Exception as exc:  # pragma: no cover - depends on network
            _logger.warning("Remote image generation failed: %s", exc)
            return []

        if not isinstance(pil_image, Image.Image):  # pragma: no cover - API contract
            _logger.warning("Unexpected image payload from inference API: %s", type(pil_image))
            return []

        palette = _extract_palette(pil_image)
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        filename = f"{timestamp.strftime('%Y%m%d%H%M%S')}_{seed}.png"
        relative_path = Path("imageforge") / filename
        (output_dir / filename).write_bytes(buffer.getvalue())

        results.append(
            GeneratedImage(
                identifier=seed,
                prompt=original_prompt,
                relative_path=str(relative_path).replace("\\", "/"),
                mime_type="image/png",
                palette=palette,
                created_at=timestamp,
                provider="huggingface",
                caption=caption,
                director_prompt=director_prompt,
            )
        )

    return results


def _enhance_prompt(prompt: str) -> Tuple[str, str]:
    """Use GPT-OSS to craft a rich art direction and caption."""

    trimmed = prompt.strip() or "Untitled concept"
    instructions = (
        "You are GPT-OSS-20B acting as an art director. Given the idea below, "
        "write a single vivid diffusion prompt and a short caption. Respond "
        "with exactly two lines:\n"
        "PROMPT: <the expanded diffusion prompt>\n"
        "CAPTION: <a friendly caption for the gallery card>.\n"
        f"Idea: {trimmed}"
    )

    completion = remote_text(instructions, max_new_tokens=220, temperature=0.65, top_p=0.92)
    if not completion:
        return trimmed, trimmed

    prompt_match = re.search(r"PROMPT:\s*(.+)", completion, re.IGNORECASE)
    caption_match = re.search(r"CAPTION:\s*(.+)", completion, re.IGNORECASE)

    expanded_prompt = prompt_match.group(1).strip() if prompt_match else trimmed
    caption = caption_match.group(1).strip() if caption_match else trimmed

    return expanded_prompt or trimmed, caption or trimmed


def generate_images(prompt: str, count: int) -> List[GeneratedImage]:
    """Generate creative assets, falling back to SVG placeholders if needed."""

    prompt = prompt.strip() or "Untitled concept"
    count = max(1, min(int(count or 1), 8))

    director_prompt, caption = _enhance_prompt(prompt)

    via_hf = list(_generate_via_huggingface(director_prompt, count, caption, prompt))
    if via_hf:
        return via_hf

    placeholders = forge_images(
        prompt,
        count,
        caption=caption,
        director_prompt=director_prompt,
    )
    return [
        GeneratedImage(
            identifier=item.identifier,
            prompt=item.prompt,
            relative_path=item.relative_path,
            mime_type="image/svg+xml",
            palette=item.palette,
            created_at=item.created_at,
            provider="placeholder",
            caption=item.caption,
            director_prompt=item.director_prompt,
        )
        for item in placeholders
    ]
