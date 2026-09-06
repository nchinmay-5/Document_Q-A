"""Turns a follow-up question into a standalone retrieval query.

One LLM call, no agent. A first question in a conversation needs no rewriting,
so the call is skipped entirely — and a rewriter failure falls back to the
original question rather than failing the request.
"""
import logging
from dataclasses import dataclass

from django.conf import settings

from generation.llm import LLMError, get_llm_client
from generation.prompts import REWRITE_SYSTEM_PROMPT, build_rewrite_prompt

logger = logging.getLogger(__name__)

MAX_REWRITE_CHARS = 500


@dataclass(frozen=True)
class RewrittenQuery:
    """The query actually sent to retrieval, next to what the user typed."""

    original: str
    rewritten: str
    rewritten_by_llm: bool
    reason: str  # why rewriting ran or was skipped

    def describe(self) -> dict:
        return {
            "original_query": self.original,
            "rewritten_query": self.rewritten,
            "rewritten_by_llm": self.rewritten_by_llm,
            "reason": self.reason,
        }


def _unchanged(question: str, reason: str) -> RewrittenQuery:
    return RewrittenQuery(
        original=question, rewritten=question, rewritten_by_llm=False, reason=reason
    )


def format_history(history: list[dict], turns: int) -> str:
    """Render the most recent turns as plain 'Role: text' lines."""
    lines = [
        f"{turn.get('role', 'user').capitalize()}: {turn.get('content', '').strip()}"
        for turn in history[-turns:]
        if turn.get("content")
    ]
    return "\n".join(lines)


def rewrite_query(question: str, history: list[dict] | None = None) -> RewrittenQuery:
    """Resolve a follow-up question against recent conversation history."""
    if not settings.QUERY_REWRITE_ENABLED:
        return _unchanged(question, "disabled")

    formatted = format_history(history or [], settings.QUERY_REWRITE_HISTORY_TURNS)
    if not formatted:
        return _unchanged(question, "no history")

    try:
        rewritten = get_llm_client().generate(
            system_prompt=REWRITE_SYSTEM_PROMPT,
            user_prompt=build_rewrite_prompt(question, formatted),
        )
    except LLMError as exc:
        # Retrieval on the raw question is far better than no answer at all.
        logger.warning("Query rewriting failed, using the original question: %s", exc)
        return _unchanged(question, "rewriter failed")

    # A model that ignores the single-line instruction should not poison the query.
    rewritten = rewritten.strip().splitlines()[0].strip().strip('"')
    if not rewritten or len(rewritten) > MAX_REWRITE_CHARS:
        return _unchanged(question, "rewrite rejected")

    return RewrittenQuery(
        original=question, rewritten=rewritten, rewritten_by_llm=True, reason="follow-up resolved"
    )
