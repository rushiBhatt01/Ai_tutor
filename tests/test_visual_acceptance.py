from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from functions.visual_acceptance import (
    AttemptBudget, Check, Decision, Verdict, candidate_checks, evaluate_checks,
)


def test_playable_but_semantically_wrong_visual_retries_then_falls_back():
    budget = AttemptBudget(max_attempts=2)
    budget.begin()
    checks = candidate_checks(spec_valid=True, media_valid=True, semantic_valid=False)
    assert evaluate_checks(checks, budget).decision is Decision.RETRY
    budget.begin()
    result = evaluate_checks(checks, budget)
    assert result.verdict is Verdict.REJECTED
    assert result.decision is Decision.FALLBACK


def test_uncertain_relevance_never_passes():
    budget = AttemptBudget()
    budget.begin()
    result = evaluate_checks(candidate_checks(
        spec_valid=True, media_valid=True, semantic_valid=None,
        source_eligible=True,
    ), budget)
    assert result.verdict is Verdict.UNCERTAIN
    assert result.decision is Decision.RETRY


def test_ineligible_source_bypasses_retry():
    budget = AttemptBudget()
    budget.begin()
    result = evaluate_checks(candidate_checks(
        spec_valid=True, media_valid=True, source_eligible=False,
    ), budget)
    assert result.decision is Decision.FAIL
    assert not result.retryable


def test_hard_failure_bypasses_retry():
    budget = AttemptBudget()
    budget.begin()
    result = evaluate_checks([Check(
        name="worker", passed=False, reason_code="worker_crashed",
    )], budget, hard_failure=True)
    assert result.decision is Decision.FAIL
    assert not result.retryable


def test_hard_failure_overrides_passing_checks():
    budget = AttemptBudget()
    budget.begin()
    result = evaluate_checks(candidate_checks(
        spec_valid=True, media_valid=True, semantic_valid=True,
    ), budget, hard_failure=True)
    assert result.verdict is Verdict.REJECTED
    assert result.decision is Decision.FAIL
    assert "hard_failure" in result.reason_codes


def test_expired_time_budget_routes_retryable_failure_to_fallback(monkeypatch):
    budget = AttemptBudget(max_attempts=3, max_elapsed_seconds=0.01)
    budget.begin()
    monkeypatch.setattr("functions.visual_acceptance.monotonic", lambda: budget.started_at + 1)
    result = evaluate_checks([Check(
        name="media", passed=False, reason_code="conversion_failed",
    )], budget)
    assert result.decision is Decision.FALLBACK


def test_attempt_budget_cannot_be_reset_by_begin():
    budget = AttemptBudget(max_attempts=1)
    assert budget.begin() == 1
    with pytest.raises(RuntimeError, match="exhausted"):
        budget.begin()
