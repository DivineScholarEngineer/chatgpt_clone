from __future__ import annotations

import hashlib
import html
import random
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List

from django.conf import settings
from django.utils import timezone
from posixpath import join as url_path_join


@dataclass
class ForgedImage:
    """Metadata about a generated placeholder image."""

    identifier: str
    prompt: str
    relative_path: str
    palette: List[str]
    created_at: datetime
    caption: str
    director_prompt: str

    @property
    def filename(self) -> str:
        return Path(self.relative_path).name

    @property
    def url(self) -> str:
        base = str(settings.MEDIA_URL).rstrip("/") or "/"
        return url_path_join(base, self.relative_path)


def _ensure_output_dir() -> Path:
    target = Path(settings.MEDIA_ROOT) / "imageforge"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _derive_palette(seed: str) -> List[str]:
    shades = []
    for index in range(3):
        start = index * 6
        segment = seed[start : start + 6]
        if len(segment) < 6:
            segment = (segment * 2)[:6]
        shades.append(f"#{segment}")
    return shades


def _build_svg(prompt: str, palette: List[str], seed_int: int) -> str:
    width, height = 768, 768
    gradient_id = f"grad-{seed_int:x}"[:12]
    rng = random.Random(seed_int)
    escaped_prompt = html.escape(prompt)
    wrapped_prompt = textwrap.wrap(escaped_prompt, width=28) or ["Vision in progress"]
    line_height = 34
    start_y = height / 2 - (len(wrapped_prompt) - 1) * (line_height / 2)

    circles = []
    for colour in palette:
        radius = rng.randint(120, 220)
        cx = rng.randint(0, width)
        cy = rng.randint(0, height)
        opacity = rng.uniform(0.18, 0.32)
        circles.append(
            f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="{colour}" opacity="{opacity:.2f}" />'
        )

    text_lines = []
    for offset, line in enumerate(wrapped_prompt):
        y_position = start_y + offset * line_height
        text_lines.append(
            f'<text x="50%" y="{y_position:.1f}" text-anchor="middle" '
            f'font-family="Segoe UI, Helvetica Neue, Arial, sans-serif" '
            f'font-size="26" fill="#0f172a" opacity="0.9">{line}</text>'
        )

    gradient_stops = []
    for idx, colour in enumerate(palette):
        offset = int((idx / max(1, len(palette) - 1)) * 100)
        gradient_stops.append(
            f'<stop offset="{offset}%" stop-color="{colour}" stop-opacity="0.95" />'
        )

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        f"  <defs>\n"
        f"    <linearGradient id=\"{gradient_id}\" x1=\"0%\" y1=\"0%\" x2=\"100%\" y2=\"100%\">\n"
        + "\n".join(f"      {stop}" for stop in gradient_stops)
        + "\n"
        "    </linearGradient>\n"
        "  </defs>\n"
        f"  <rect width=\"{width}\" height=\"{height}\" fill=\"url(#{gradient_id})\" rx=\"42\" />\n"
        + "\n".join(f"  {circle}" for circle in circles)
        + "\n"
        + "\n".join(f"  {line}" for line in text_lines)
        + "\n"
        "</svg>\n"
    )


def forge_images(
    prompt: str,
    count: int,
    *,
    caption: str | None = None,
    director_prompt: str | None = None,
) -> List[ForgedImage]:
    """Create decorative SVG placeholders for the requested prompt."""

    output_dir = _ensure_output_dir()
    trimmed_prompt = prompt.strip() or "Untitled concept"
    timestamp = timezone.now()
    results: List[ForgedImage] = []

    for index in range(count):
        seed_input = f"{trimmed_prompt}:{timestamp.isoformat()}:{index}".encode("utf-8")
        digest = hashlib.sha1(seed_input).hexdigest()
        palette = _derive_palette(digest)
        svg_content = _build_svg(trimmed_prompt, palette, int(digest[:12], 16))
        filename = f"{timestamp.strftime('%Y%m%d%H%M%S')}_{digest[:10]}.svg"
        relative_path = Path("imageforge") / filename
        (output_dir / filename).write_text(svg_content, encoding="utf-8")

        results.append(
            ForgedImage(
                identifier=digest[:16],
                prompt=trimmed_prompt,
                relative_path=str(relative_path).replace("\\", "/"),
                palette=palette,
                created_at=timestamp,
                caption=caption or trimmed_prompt,
                director_prompt=director_prompt or trimmed_prompt,
            )
        )

    return results
