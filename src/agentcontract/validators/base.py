"""Base validator interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunContext:
    """Everything a validator knows about a single agent run."""
    input: str
    output: str
    duration_ms: float = 0.0
    cost_usd: float = 0.0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    steps: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    passed: bool
    clause_name: str
    clause_text: str
    clause_type: str
    judge: str = "deterministic"
    details: str = ""


class Validator(ABC):
    """Abstract base for all validators."""

    @abstractmethod
    def validate(self, context: RunContext) -> ValidationResult:
        ...
