"""@enforce decorator — wraps any agent function with contract validation."""

from __future__ import annotations

import functools
import time
from pathlib import Path
from typing import Any, Callable

from .exceptions import ContractPreconditionError, ContractViolation
from .loader import load_contract
from .models import Contract, JudgeType
from .runner import ContractRunner, RunContext
from .validators.llm import LLMValidator


def enforce(
    contract: Contract | str | Path,
    *,
    audit: bool = True,
    audit_path: str | Path = "agentcontract-audit.jsonl",
    cost_fn: Callable[..., float] | None = None,
) -> Callable:
    """
    Decorator that enforces an AgentContract on any agent function.

    Usage:
        contract = Contract.load("my-agent.contract.yaml")

        @enforce(contract)
        def run_agent(user_input: str) -> str:
            return my_llm.run(user_input)

    Args:
        contract:   A Contract instance, or path to a .contract.yaml file.
        audit:      Whether to write to the audit log. Default: True.
        audit_path: Path to the JSONL audit log file.
        cost_fn:    Optional callable that returns cost_usd from the function's return value.
    """
    if isinstance(contract, (str, Path)):
        _contract = load_contract(contract)
    else:
        _contract = contract

    runner = ContractRunner(_contract)

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Resolve input string from first positional arg or 'input'/'user_input' kwarg
            input_str = ""
            if args:
                input_str = str(args[0])
            elif "input" in kwargs:
                input_str = str(kwargs["input"])
            elif "user_input" in kwargs:
                input_str = str(kwargs["user_input"])

            # Check preconditions
            _check_preconditions(_contract, input_str)

            # Run the agent, measuring timing
            start = time.perf_counter()
            result_value = fn(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000

            output_str = str(result_value) if result_value is not None else ""
            cost_usd = cost_fn(result_value) if cost_fn else 0.0

            ctx = RunContext(
                input=input_str,
                output=output_str,
                duration_ms=duration_ms,
                cost_usd=cost_usd,
            )

            run_result = runner.run(ctx)

            if audit:
                from .audit import AuditWriter
                AuditWriter(audit_path).write(run_result, contract_path=str(
                    contract if isinstance(contract, (str, Path)) else ""
                ))

            blocking = run_result.blocking_violations()
            if blocking:
                raise ContractViolation([
                    {
                        "clause_type": v.clause_type,
                        "clause_text": v.clause_text,
                        "action_taken": v.action_taken,
                    }
                    for v in blocking
                ])

            # Warn-level violations: print to stderr
            warn_violations = [v for v in run_result.violations if v.action_taken == "warn"]
            if warn_violations:
                import sys
                for v in warn_violations:
                    print(
                        f"[AgentContract WARN] {v.clause_type.upper()}: \"{v.clause_text}\" — {v.details}",
                        file=sys.stderr,
                    )

            return result_value

        return wrapper

    return decorator


def _check_preconditions(contract: Contract, input_str: str) -> None:
    """Evaluate requires: clauses before the agent runs."""
    for precondition in contract.requires:
        if isinstance(precondition, str):
            text = precondition
            judge = JudgeType.DETERMINISTIC
            on_fail = "block"
        else:
            text = precondition.text
            judge = precondition.judge
            on_fail = precondition.on_fail.value

        passed = True
        details = ""

        if judge == JudgeType.DETERMINISTIC:
            # Built-in deterministic precondition checks
            if "non-empty" in text.lower() or "not empty" in text.lower():
                passed = bool(input_str.strip())
                details = "Input is empty." if not passed else ""
        elif judge == JudgeType.LLM:
            ctx = RunContext(input=input_str, output="")
            result = LLMValidator(
                name=f"requires:{text[:30]}",
                clause_text=text,
                clause_type="requires",
            ).validate(ctx)
            passed = result.passed
            details = result.details

        if not passed and on_fail == "block":
            raise ContractPreconditionError(clause=text, details=details)
