"""JSON Schema validator."""

from __future__ import annotations

import json
from typing import Any

from .base import RunContext, ValidationResult, Validator


class SchemaValidator(Validator):
    """Validates that agent output conforms to a JSON Schema."""

    def __init__(self, name: str, schema: dict[str, Any], description: str = "") -> None:
        self.name = name
        self.schema = schema
        self.description = description

    def validate(self, context: RunContext) -> ValidationResult:
        try:
            import jsonschema
        except ImportError:
            return ValidationResult(
                passed=False,
                clause_name=self.name,
                clause_text=self.description or self.name,
                clause_type="assert",
                judge="deterministic",
                details="jsonschema package not installed. Run: pip install agentcontract[schema]",
            )

        try:
            output = json.loads(context.output)
        except json.JSONDecodeError as e:
            return ValidationResult(
                passed=False,
                clause_name=self.name,
                clause_text=self.description or self.name,
                clause_type="assert",
                judge="deterministic",
                details=f"Output is not valid JSON: {e}",
            )

        try:
            jsonschema.validate(instance=output, schema=self.schema)
            return ValidationResult(
                passed=True,
                clause_name=self.name,
                clause_text=self.description or self.name,
                clause_type="assert",
                judge="deterministic",
            )
        except jsonschema.ValidationError as e:
            return ValidationResult(
                passed=False,
                clause_name=self.name,
                clause_text=self.description or self.name,
                clause_type="assert",
                judge="deterministic",
                details=f"Schema validation failed: {e.message}",
            )
