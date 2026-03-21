"""
AgentContract — Behavioral contracts for AI agents.

Python reference implementation of the AgentContract specification.
https://github.com/agentcontract/spec
"""

from .enforce import enforce
from .exceptions import ContractError, ContractLoadError, ContractPreconditionError, ContractViolation
from .loader import load_contract
from .models import Contract
from .runner import ContractRunner, RunContext, RunResult

__version__ = "0.1.0"
__spec_version__ = "0.1.0"
__all__ = [
    "Contract",
    "ContractRunner",
    "RunContext",
    "RunResult",
    "load_contract",
    "enforce",
    "ContractError",
    "ContractLoadError",
    "ContractPreconditionError",
    "ContractViolation",
]
