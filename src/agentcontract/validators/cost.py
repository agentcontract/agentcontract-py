"""Cost validator."""

from __future__ import annotations

from .base import RunContext, ValidationResult, Validator


class CostValidator(Validator):
    """Validates that run cost does not exceed the configured maximum."""

    def __init__(self, name: str, max_usd: float, description: str = "") -> None:
        self.name = name
        self.max_usd = max_usd
        self.description = description

    def validate(self, context: RunContext) -> ValidationResult:
        passed = context.cost_usd <= self.max_usd
        return ValidationResult(
            passed=passed,
            clause_name=self.name,
            clause_text=self.description or f"cost must not exceed ${self.max_usd:.4f} USD",
            clause_type="assert",
            judge="deterministic",
            details="" if passed else (
                f"Run cost ${context.cost_usd:.4f} exceeded limit ${self.max_usd:.4f}"
            ),
        )
