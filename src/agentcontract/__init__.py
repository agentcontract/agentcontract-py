"""
AgentContract — Behavioral contracts for AI agents.

Python reference implementation of the AgentContract specification.
https://github.com/agentcontract/spec
"""

from .audit import AuditWriter
from .enforce import enforce
from .exceptions import ContractError, ContractLoadError, ContractPreconditionError, ContractViolation
from .loader import load_contract
from .models import Contract
from .runner import ContractRunner, OutcomeResult, RunContext, RunResult

__version__ = "0.2.0"
__spec_version__ = "0.2.0"
__all__ = [
    "AuditWriter",
    "Contract",
    "ContractRunner",
    "OutcomeResult",
    "RunContext",
    "RunResult",
    "load_contract",
    "enforce",
    "ContractError",
    "ContractLoadError",
    "ContractPreconditionError",
    "ContractViolation",
]
