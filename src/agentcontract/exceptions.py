"""AgentContract exceptions."""

from __future__ import annotations


class ContractError(Exception):
    """Base class for all AgentContract errors."""


class ContractLoadError(ContractError):
    """Raised when a contract file cannot be loaded or is invalid."""


class ContractPreconditionError(ContractError):
    """Raised when a precondition (requires:) clause fails before the agent runs."""

    def __init__(self, clause: str, details: str = "") -> None:
        self.clause = clause
        self.details = details
        super().__init__(f"[PRECONDITION FAILED] {clause}" + (f": {details}" if details else ""))


class ContractViolation(ContractError):
    """Raised when a blocking clause is violated during or after a run."""

    def __init__(self, violations: list[dict]) -> None:
        self.violations = violations
        lines = []
        for v in violations:
            lines.append(
                f"[{v['action_taken'].upper()}] {v['clause_type'].upper()}: \"{v['clause_text']}\""
            )
        super().__init__("AgentContractViolation:\n" + "\n".join(lines))
