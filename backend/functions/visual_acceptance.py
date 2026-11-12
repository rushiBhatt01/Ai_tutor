"""Shared, auditable acceptance decisions for generated scene visuals."""

from dataclasses import dataclass
from enum import Enum
from time import monotonic
from typing import Iterable, Optional

from pydantic import BaseModel, ConfigDict, Field


EVALUATOR_VERSION = "visual-acceptance-v3"


class Verdict(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"


class Decision(str, Enum):
    ACCEPT = "accept"
    RETRY = "retry"
    FALLBACK = "fallback"
    FAIL = "fail"


class Check(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    passed: Optional[bool]
    reason_code: str
    evidence: list[str] = Field(default_factory=list)
    retryable: bool = True


class AcceptanceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: Verdict
    decision: Decision
    reason_codes: list[str]
    evidence: list[str]
    evaluator_version: str = EVALUATOR_VERSION
    retryable: bool
    attempt: int = Field(ge=1)
    elapsed_seconds: float = Field(ge=0)


@dataclass
class AttemptBudget:
    """One shared budget object; retries must reuse it rather than reset counters."""

    max_attempts: int = 2
    max_elapsed_seconds: float = 300.0
    started_at: float = 0.0
    attempts: int = 0

    def __post_init__(self):
        if self.max_attempts < 1 or self.max_elapsed_seconds <= 0:
            raise ValueError("Attempt budget limits must be positive")
        if not self.started_at:
            self.started_at = monotonic()

    @property
    def elapsed_seconds(self) -> float:
        return max(0.0, monotonic() - self.started_at)

    def begin(self) -> int:
        if not self.can_attempt:
            raise RuntimeError("Visual attempt budget exhausted")
        self.attempts += 1
        return self.attempts

    @property
    def can_attempt(self) -> bool:
        return self.attempts < self.max_attempts and self.elapsed_seconds < self.max_elapsed_seconds


def evaluate_checks(checks: Iterable[Check], budget: AttemptBudget, *, hard_failure=False) -> AcceptanceResult:
    """Combine independent checks. Missing/uncertain evidence can never pass acceptance."""
    checks = list(checks)
    if hard_failure:
        checks.append(Check(name="execution", passed=False,
                            reason_code="hard_failure", retryable=False))
    if not checks:
        checks = [Check(name="evidence", passed=None, reason_code="no_validation_evidence")]
    failed = [check for check in checks if check.passed is False]
    uncertain = [check for check in checks if check.passed is None]
    reasons = [check.reason_code for check in failed + uncertain]
    evidence = [f"{check.name}: {item}" for check in checks for item in check.evidence]
    if not failed and not uncertain:
        verdict, decision, retryable = Verdict.ACCEPTED, Decision.ACCEPT, False
    else:
        retryable = (
            not hard_failure
            and not any(check.passed is False and not check.retryable for check in checks)
            and any(check.retryable for check in failed + uncertain)
        )
        if hard_failure:
            verdict, decision = Verdict.REJECTED, Decision.FAIL
        elif retryable and budget.can_attempt:
            verdict, decision = (Verdict.UNCERTAIN if uncertain and not failed else Verdict.REJECTED), Decision.RETRY
        elif retryable:
            verdict, decision = (Verdict.UNCERTAIN if uncertain and not failed else Verdict.REJECTED), Decision.FALLBACK
        else:
            verdict, decision = Verdict.REJECTED, Decision.FAIL
    return AcceptanceResult(
        verdict=verdict, decision=decision, reason_codes=reasons,
        evidence=evidence, retryable=retryable, attempt=max(1, budget.attempts),
        elapsed_seconds=round(budget.elapsed_seconds, 3),
    )


def candidate_checks(*, spec_valid, media_valid, semantic_valid=None,
                     source_eligible=None, algorithm_valid=None):
    """Build standard checks; providers/renderers supply explicit evidence booleans."""
    checks = [
        Check(name="spec", passed=spec_valid, reason_code="invalid_spec"),
        Check(name="media", passed=media_valid, reason_code="invalid_media"),
    ]
    if algorithm_valid is not None:
        checks.append(Check(name="algorithm", passed=algorithm_valid, reason_code="algorithm_invariant_failed"))
    if source_eligible is not None:
        checks.append(Check(name="source", passed=source_eligible, reason_code="source_license_ineligible", retryable=False))
    checks.append(Check(name="semantic", passed=semantic_valid,
                        reason_code="semantic_uncertain" if semantic_valid is None else "semantic_mismatch"))
    return checks
