"""Regex pattern validator."""

from __future__ import annotations

import re

from .base import RunContext, ValidationResult, Validator


class PatternValidator(Validator):
    """Validates output against regex patterns (must_match / must_not_match)."""

    def __init__(
        self,
        name: str,
        must_not_match: str | None = None,
        must_match: str | None = None,
        description: str = "",
    ) -> None:
        self.name = name
        self.must_not_match = must_not_match
        self.must_match = must_match
        self.description = description

    def validate(self, context: RunContext) -> ValidationResult:
        output = context.output

        if self.must_not_match:
            match = re.search(self.must_not_match, output)
            if match:
                return ValidationResult(
                    passed=False,
                    clause_name=self.name,
                    clause_text=self.description or f"must_not_match: {self.must_not_match}",
                    clause_type="assert",
                    judge="deterministic",
                    details=f"Forbidden pattern found at position {match.start()}: '{match.group()[:50]}'",
                )

        if self.must_match:
            match = re.search(self.must_match, output)
            if not match:
                return ValidationResult(
                    passed=False,
                    clause_name=self.name,
                    clause_text=self.description or f"must_match: {self.must_match}",
                    clause_type="assert",
                    judge="deterministic",
                    details="Required pattern not found in output.",
                )

        return ValidationResult(
            passed=True,
            clause_name=self.name,
            clause_text=self.description or self.name,
            clause_type="assert",
            judge="deterministic",
        )
