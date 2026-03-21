"""Tests for contract loading and the runner."""

import pytest
from pathlib import Path

from agentcontract import load_contract, ContractRunner, RunContext
from agentcontract.exceptions import ContractLoadError


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def create_fixtures(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def write_contract(tmp_path, content: str) -> Path:
    p = tmp_path / "test.contract.yaml"
    p.write_text(content)
    return p


class TestContractLoading:
    def test_minimal_valid_contract(self, tmp_path):
        p = write_contract(tmp_path, """
agent: my-agent
spec-version: 0.1.0
version: 1.0.0
on_violation:
  default: block
""")
        c = load_contract(p)
        assert c.agent == "my-agent"
        assert c.version == "1.0.0"

    def test_missing_required_field_raises(self, tmp_path):
        p = write_contract(tmp_path, """
spec-version: 0.1.0
version: 1.0.0
""")
        with pytest.raises(ContractLoadError):
            load_contract(p)

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(ContractLoadError, match="not found"):
            load_contract(tmp_path / "nonexistent.contract.yaml")

    def test_invalid_yaml_raises(self, tmp_path):
        p = tmp_path / "bad.contract.yaml"
        p.write_text("{ invalid yaml: [")
        with pytest.raises(ContractLoadError):
            load_contract(p)

    def test_full_contract_loads(self, tmp_path):
        p = write_contract(tmp_path, """
agent: support-bot
spec-version: 0.1.0
version: 2.0.0
description: Full test contract
tags: [test, support]

must:
  - respond in the user's language
  - text: escalate if confidence low
    judge: llm

must_not:
  - reveal system prompt

can:
  - query knowledge base

limits:
  max_tokens: 500
  max_latency_ms: 30000
  max_cost_usd: 0.05

assert:
  - name: no_pii
    type: pattern
    must_not_match: "\\\\d{4}-\\\\d{4}"
    description: No card numbers

on_violation:
  default: block
  no_pii: halt_and_alert
""")
        c = load_contract(p)
        assert len(c.must) == 2
        assert len(c.must_not) == 1
        assert len(c.assert_) == 1
        assert c.on_violation.action_for("no_pii").value == "halt_and_alert"
        assert c.on_violation.action_for("anything_else").value == "block"


class TestContractRunner:
    def test_passes_clean_output(self, tmp_path):
        p = write_contract(tmp_path, """
agent: test-agent
spec-version: 0.1.0
version: 1.0.0
assert:
  - name: no_credit_card
    type: pattern
    must_not_match: "\\\\d{4}[- ]\\\\d{4}"
on_violation:
  default: block
""")
        contract = load_contract(p)
        runner = ContractRunner(contract)
        ctx = RunContext(input="hello", output="Here is your answer.")
        result = runner.run(ctx)
        assert result.passed
        assert result.violations == []

    def test_catches_pattern_violation(self, tmp_path):
        p = write_contract(tmp_path, """
agent: test-agent
spec-version: 0.1.0
version: 1.0.0
assert:
  - name: no_credit_card
    type: pattern
    must_not_match: "\\\\d{4}[- ]\\\\d{4}"
on_violation:
  default: block
""")
        contract = load_contract(p)
        runner = ContractRunner(contract)
        ctx = RunContext(input="hello", output="Your card 1234-5678 was processed.")
        result = runner.run(ctx)
        assert not result.passed
        assert any(v.clause_name == "no_credit_card" for v in result.violations)

    def test_latency_violation(self, tmp_path):
        p = write_contract(tmp_path, """
agent: test-agent
spec-version: 0.1.0
version: 1.0.0
limits:
  max_latency_ms: 100
on_violation:
  default: warn
""")
        contract = load_contract(p)
        runner = ContractRunner(contract)
        ctx = RunContext(input="hello", output="ok", duration_ms=500)
        result = runner.run(ctx)
        assert any(v.clause_name == "max_latency_ms" for v in result.violations)
        # warn-only → still passes
        assert result.passed

    def test_warn_violations_do_not_block(self, tmp_path):
        p = write_contract(tmp_path, """
agent: test-agent
spec-version: 0.1.0
version: 1.0.0
assert:
  - name: slow_response
    type: latency
    max_ms: 10
on_violation:
  default: warn
""")
        contract = load_contract(p)
        runner = ContractRunner(contract)
        ctx = RunContext(input="hello", output="ok", duration_ms=5000)
        result = runner.run(ctx)
        assert result.passed  # warn only
        assert len(result.violations) == 1
