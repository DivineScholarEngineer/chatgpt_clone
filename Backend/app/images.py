"""Text-to-image helpers with graceful fallbacks."""
from __future__ import annotations

import io
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from django.conf import settings
from django.utils import timezone
from posixpath import join as url_path_join

try:  # pragma: no cover - optional dependencies
    from PIL import Image
except ImportError:  # pragma: no cover - optional dependencies
    Image = None  # type: ignore[assignment]

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


def _generate_via_huggingface(prompt: str, count: int) -> Iterable[GeneratedImage]:
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

    for _ in range(count):
        seed = secrets.token_hex(8)
        try:
            pil_image = client.text_to_image(
                prompt,
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
                prompt=prompt,
                relative_path=str(relative_path).replace("\\", "/"),
                mime_type="image/png",
                palette=palette,
                created_at=timestamp,
                provider="huggingface",
            )
        )

    return results


def generate_images(prompt: str, count: int) -> List[GeneratedImage]:
    """Generate creative assets, falling back to SVG placeholders if needed."""

    prompt = prompt.strip() or "Untitled concept"
    count = max(1, min(int(count or 1), 8))

    via_hf = list(_generate_via_huggingface(prompt, count))
    if via_hf:
        return via_hf

    placeholders = forge_images(prompt, count)
    return [
        GeneratedImage(
            identifier=item.identifier,
            prompt=item.prompt,
            relative_path=item.relative_path,
            mime_type="image/svg+xml",
            palette=item.palette,
            created_at=item.created_at,
            provider="placeholder",
        )
        for item in placeholders
    ]
