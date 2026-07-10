"""
tests/test_tooling_smoke.py

Module 0 smoke test — verifies the pytest infrastructure itself is working.
This file intentionally tests nothing project-specific; it exists so that
`make test` passes on a fresh checkout and CI has a baseline green signal.
"""


def test_true() -> None:
    """Trivial assertion to confirm pytest is collected and running."""
    assert True


def test_fixtures_importable(  # type: ignore[no-untyped-def]
    sample_trace,
    sample_llm_call_span,
    sample_tool_call_span,
    sample_rag_span,
):
    """
    Confirm all four shared fixtures from conftest.py can be resolved and
    return non-None values — i.e. the Pydantic models import cleanly.
    """
    assert sample_trace is not None
    assert sample_llm_call_span is not None
    assert sample_tool_call_span is not None
    assert sample_rag_span is not None
