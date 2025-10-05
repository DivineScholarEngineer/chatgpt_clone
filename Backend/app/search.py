"""Lightweight web search integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

import requests

_logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    title: str
    excerpt: str
    url: str
    source: str


def perform_web_search(query: str) -> List[SearchResult]:
    """Query DuckDuckGo's instant answer API and return curated results."""

    params = {
        "q": query,
        "format": "json",
        "no_html": 1,
        "skip_disambig": 1,
    }

    try:
        response = requests.get(
            "https://api.duckduckgo.com/", params=params, timeout=8
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # pragma: no cover - network dependent
        _logger.warning("Web search failed: %s", exc)
        return []

    results: List[SearchResult] = []

    def _add_result(title: str, excerpt: str, url: str) -> None:
        if not title or not url:
            return
        results.append(
            SearchResult(
                title=title.strip(),
                excerpt=excerpt.strip() if excerpt else "",
                url=url.strip(),
                source="DuckDuckGo",
            )
        )

    heading = payload.get("Heading")
    abstract = payload.get("AbstractText")
    abstract_url = payload.get("AbstractURL")
    if heading and abstract_url:
        _add_result(heading, abstract or "", abstract_url)

    related = payload.get("RelatedTopics") or []
    for entry in related:
        if isinstance(entry, dict) and "FirstURL" in entry:
            _add_result(entry.get("Text", ""), entry.get("Text", ""), entry["FirstURL"])
        elif isinstance(entry, dict) and "Topics" in entry:
            for topic in entry.get("Topics", []):
                if isinstance(topic, dict) and "FirstURL" in topic:
                    _add_result(topic.get("Text", ""), topic.get("Text", ""), topic["FirstURL"])
        if len(results) >= 6:
            break

    return results
