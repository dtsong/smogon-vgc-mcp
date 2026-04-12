"""Pluggable pre-fill for the labeler form.

The labeler can optionally ask a Tier-1 extractor to pre-populate the
form with its best guess at the Pokemon sets in an article. The UI
then surfaces which fields the labeler corrected, and those deltas are
recorded on save for per-field F1 evaluation of the extractor.

Two implementations:

- :class:`StubPrefiller` — returns nothing. Always available, keeps
  the labeler runnable offline and in tests.
- :class:`AnthropicPrefiller` — calls Claude Haiku 4.5 with a minimal
  system prompt and asks it to emit JSON matching the labeler's set
  schema. Active only when ``ANTHROPIC_API_KEY`` is set.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

_SYSTEM_PROMPT = """You extract competitive VGC Pokemon sets from historical tournament articles.

Return ONLY valid JSON matching this shape:
{"sets": [{"pokemon": "Name", "ability": "...", "item": "...", "nature": "...",
           "tera_type": null, "ev_hp": 0, "ev_atk": 0, "ev_def": 0,
           "ev_spa": 0, "ev_spd": 0, "ev_spe": 0, "move1": "...", "move2": "...",
           "move3": "...", "move4": "...", "level": 50, "raw_snippet": "..."}]}

Rules:
- Only include a set if the article explicitly declares the Pokemon.
- Use null for any field the article does not state. Never guess.
- tera_type is always null for articles published before 2022.
- raw_snippet must be a verbatim quote (≤300 chars) from the article
  that supports the set.
- If the article contains no sets, return {"sets": []}.
"""

_MAX_INPUT_CHARS = 16000


class Prefiller(Protocol):
    """Returns a list of pre-filled set dicts for an article body."""

    name: str
    available: bool

    async def prefill(self, *, title: str, content_text: str) -> list[dict[str, Any]]: ...


class StubPrefiller:
    name: str = "stub"
    available: bool = True

    async def prefill(self, *, title: str, content_text: str) -> list[dict[str, Any]]:
        return []


class AnthropicPrefiller:
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

    async def prefill(self, *, title: str, content_text: str) -> list[dict[str, Any]]:
        if not self.available:
            return []
        client = self._get_client()
        body = (content_text or "")[:_MAX_INPUT_CHARS]
        msg = await client.messages.create(
            model=self.model,
            max_tokens=2048,
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
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return []
        sets = parsed.get("sets") if isinstance(parsed, dict) else None
        return sets if isinstance(sets, list) else []


def get_default_prefiller() -> Prefiller:
    """Pick the best-available prefiller for the current environment."""
    anthropic_prefiller = AnthropicPrefiller()
    if anthropic_prefiller.available:
        return anthropic_prefiller
    return StubPrefiller()
