"""Batch article triage via LLM classification.

Runs a cheap Haiku pass over each untriaged article to classify it as
``has_sets`` (contains competitive Pokemon builds worth labeling) or
``no_sets`` (news, announcements, meta discussion, etc.). The labeler
then defaults to showing only ``has_sets`` articles.

Source-agnostic — works with any ArticleSource adapter.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

_SYSTEM_PROMPT = """You classify competitive Pokemon articles.

Given an article title and body, determine whether the article contains
specific competitive Pokemon set information (species + at least some of:
ability, item, nature, EVs, moves).

Return ONLY valid JSON: {"has_sets": true} or {"has_sets": false}

Examples of has_sets=true:
- Team reports listing each Pokemon with moves/EVs/items
- Set analyses with specific builds
- Warstory/battle reports that include the author's team details

Examples of has_sets=false:
- News announcements (rule changes, event dates)
- Speed tier charts (raw stats, no builds)
- General strategy discussion without specific sets
- Site updates, community news
"""

_MAX_INPUT_CHARS = 8000


class Triager(Protocol):
    name: str
    available: bool

    async def classify(self, *, title: str, content_text: str) -> bool | None: ...


class StubTriager:
    name: str = "stub"
    available: bool = True

    async def classify(self, *, title: str, content_text: str) -> bool | None:
        return None


class AnthropicTriager:
    name: str = "claude-haiku-4-5"

    def __init__(self, model: str = "claude-haiku-4-5-20251001") -> None:
        self.model = model
        self._client: Any = None

    @property
    def available(self) -> bool:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic()
        return self._client

    async def classify(self, *, title: str, content_text: str) -> bool | None:
        if not self.available:
            return None
        client = self._get_client()
        body = (content_text or "")[:_MAX_INPUT_CHARS]
        msg = await client.messages.create(
            model=self.model,
            max_tokens=64,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Title: {title}\n\nArticle:\n{body}",
                }
            ],
        )
        text = "".join(
            block.text for block in msg.content if getattr(block, "type", None) == "text"
        ).strip()
        if not text:
            return None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict) and "has_sets" in parsed:
            return bool(parsed["has_sets"])
        return None


def get_default_triager() -> Triager:
    t = AnthropicTriager()
    if t.available:
        return t
    return StubTriager()
