"""Latency validator."""

from __future__ import annotations

from .base import RunContext, ValidationResult, Validator


class LatencyValidator(Validator):
    """Validates that run duration does not exceed the configured maximum."""

    def __init__(self, name: str, max_ms: int, description: str = "") -> None:
        self.name = name
        self.max_ms = max_ms
        self.description = description

    def validate(self, context: RunContext) -> ValidationResult:
        passed = context.duration_ms <= self.max_ms
        return ValidationResult(
            passed=passed,
            clause_name=self.name,
            clause_text=self.description or f"latency must not exceed {self.max_ms}ms",
            clause_type="assert",
            judge="deterministic",
            details="" if passed else (
                f"Run took {context.duration_ms:.0f}ms, exceeded limit of {self.max_ms}ms"
            ),
        )
