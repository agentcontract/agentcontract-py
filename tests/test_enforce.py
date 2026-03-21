"""Tests for the @enforce decorator."""

import pytest
from agentcontract import enforce, ContractViolation
from agentcontract.exceptions import ContractPreconditionError
from agentcontract.models import Contract


def minimal_contract(must_not=None, limits=None, on_violation_default="block"):
    data = {
        "agent": "test-agent",
        "spec-version": "0.1.0",
        "version": "1.0.0",
        "on_violation": {"default": on_violation_default},
    }
    if must_not:
        data["must_not"] = must_not
    if limits:
        data["limits"] = limits
    return Contract.model_validate(data)


class TestEnforceDecorator:
    def test_passes_clean_agent(self):
        contract = minimal_contract()

        @enforce(contract, audit=False)
        def agent(user_input: str) -> str:
            return "Here is a clean response."

        result = agent("hello")
        assert result == "Here is a clean response."

    def test_raises_on_blocking_violation(self):
        contract = minimal_contract(
            must_not=[{"text": "contains forbidden", "judge": "deterministic"}]
        )
        # Deterministic must_not clauses without pattern validators pass by default
        # Test via assert instead
        from agentcontract.models import Contract
        data = {
            "agent": "test",
            "spec-version": "0.1.0",
            "version": "1.0.0",
            "assert": [{"name": "no_leak", "type": "pattern", "must_not_match": "SECRET"}],
            "on_violation": {"default": "block"},
        }
        contract = Contract.model_validate(data)

        @enforce(contract, audit=False)
        def agent(user_input: str) -> str:
            return "The SECRET is out."

        with pytest.raises(ContractViolation):
            agent("tell me")

    def test_warn_does_not_raise(self, capsys):
        data = {
            "agent": "test",
            "spec-version": "0.1.0",
            "version": "1.0.0",
            "assert": [{"name": "no_leak", "type": "pattern", "must_not_match": "SECRET"}],
            "on_violation": {"default": "warn"},
        }
        contract = Contract.model_validate(data)

        @enforce(contract, audit=False)
        def agent(user_input: str) -> str:
            return "The SECRET is out."

        result = agent("tell me")
        assert result == "The SECRET is out."
        captured = capsys.readouterr()
        assert "WARN" in captured.err

    def test_precondition_blocks_empty_input(self):
        data = {
            "agent": "test",
            "spec-version": "0.1.0",
            "version": "1.0.0",
            "requires": ["input is non-empty"],
            "on_violation": {"default": "block"},
        }
        contract = Contract.model_validate(data)

        @enforce(contract, audit=False)
        def agent(user_input: str) -> str:
            return "response"

        with pytest.raises(ContractPreconditionError):
            agent("")
