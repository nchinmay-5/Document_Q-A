import pytest

from generation import query_rewriter
from generation.llm import LLMError
from generation.query_rewriter import format_history, rewrite_query

HISTORY = [
    {"role": "user", "content": "How much annual leave do employees get?"},
    {"role": "assistant", "content": "20 days. [1]"},
]


class ScriptedLLM:
    name = "scripted"

    def __init__(self, response: str):
        self._response = response

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        return self._response


@pytest.fixture
def llm(monkeypatch):
    def install(response: str | Exception):
        def get_client():
            if isinstance(response, Exception):
                raise response
            return ScriptedLLM(response)

        monkeypatch.setattr(query_rewriter, "get_llm_client", get_client)

    return install


def test_follow_up_is_rewritten_using_history(llm):
    llm("How many annual leave days do contractors get?")

    result = rewrite_query("What about contractors?", HISTORY)

    assert result.rewritten == "How many annual leave days do contractors get?"
    assert result.original == "What about contractors?"
    assert result.rewritten_by_llm


def test_first_question_skips_the_llm_call(monkeypatch):
    monkeypatch.setattr(
        query_rewriter, "get_llm_client", lambda: pytest.fail("no LLM call without history")
    )

    result = rewrite_query("How much annual leave?", [])

    assert result.rewritten == "How much annual leave?"
    assert not result.rewritten_by_llm
    assert result.reason == "no history"


def test_disabling_rewriting_leaves_the_question_alone(settings, llm):
    settings.QUERY_REWRITE_ENABLED = False
    llm("something else entirely")

    result = rewrite_query("What about contractors?", HISTORY)

    assert result.rewritten == "What about contractors?"
    assert result.reason == "disabled"


def test_rewriter_failure_falls_back_to_the_original(llm):
    llm(LLMError("provider unreachable"))

    result = rewrite_query("What about contractors?", HISTORY)

    assert result.rewritten == "What about contractors?"
    assert result.reason == "rewriter failed"


def test_only_the_first_line_of_a_chatty_rewrite_is_used(llm):
    llm('"Contractor annual leave entitlement"\n\nI hope that helps!')

    result = rewrite_query("What about contractors?", HISTORY)

    assert result.rewritten == "Contractor annual leave entitlement"


def test_an_overlong_rewrite_is_rejected(llm):
    llm("x" * 1000)

    result = rewrite_query("What about contractors?", HISTORY)

    assert result.rewritten == "What about contractors?"
    assert result.reason == "rewrite rejected"


def test_history_is_limited_to_the_recent_turns():
    turns = [{"role": "user", "content": f"q{index}"} for index in range(10)]

    formatted = format_history(turns, turns=2)

    assert formatted == "User: q8\nUser: q9"
