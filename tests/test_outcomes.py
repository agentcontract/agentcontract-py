"""Tests for outcomes clause — accessors and predicates."""

import json
import pytest
from pathlib import Path

from agentcontract import load_contract, ContractRunner, RunContext


def write_contract(tmp_path, content: str) -> Path:
    p = tmp_path / "test.contract.yaml"
    p.write_text(content)
    return p


def ctx(output="", tool_calls=None):
    return RunContext(
        input="test input",
        output=output,
        tool_calls=tool_calls or [],
    )


class TestOutputFieldAccessor:
    def test_exact_match_passes(self, tmp_path):
        p = write_contract(tmp_path, """
agent: test-agent
spec-version: 0.2.0
version: 1.0.0
outcomes:
  - name: refund_processed
    accessor:
      type: output_field
      field: "$.order.status"
      at: post-run
    predicate:
      type: exact-match
      expected: "refunded"
    on_fail: block
on_violation:
  default: block
""")
        contract = load_contract(p)
        runner = ContractRunner(contract)
        output = json.dumps({"order": {"status": "refunded"}})
        result = runner.run(ctx(output=output))
        assert result.passed
        assert len(result.outcome_results) == 1
        assert result.outcome_results[0].status == "pass"

    def test_exact_match_fails(self, tmp_path):
        p = write_contract(tmp_path, """
agent: test-agent
spec-version: 0.2.0
version: 1.0.0
outcomes:
  - name: refund_processed
    accessor:
      type: output_field
      field: "$.order.status"
      at: post-run
    predicate:
      type: exact-match
      expected: "refunded"
    on_fail: block
on_violation:
  default: block
""")
        contract = load_contract(p)
        runner = ContractRunner(contract)
        output = json.dumps({"order": {"status": "pending"}})
        result = runner.run(ctx(output=output))
        assert not result.passed
        assert result.outcome_results[0].status == "failed"
        assert any(v.clause_name == "refund_processed" for v in result.violations)

    def test_pattern_predicate_passes(self, tmp_path):
        p = write_contract(tmp_path, """
agent: test-agent
spec-version: 0.2.0
version: 1.0.0
outcomes:
  - name: ticket_id_present
    accessor:
      type: output_field
      field: "$.ticket_id"
      at: post-run
    predicate:
      type: pattern
      must_match: "^T-\\\\d+"
    on_fail: block
on_violation:
  default: block
""")
        contract = load_contract(p)
        runner = ContractRunner(contract)
        output = json.dumps({"ticket_id": "T-1042"})
        result = runner.run(ctx(output=output))
        assert result.passed
        assert result.outcome_results[0].status == "pass"

    def test_jsonpath_no_match_fails_gracefully(self, tmp_path):
        p = write_contract(tmp_path, """
agent: test-agent
spec-version: 0.2.0
version: 1.0.0
outcomes:
  - name: missing_field
    accessor:
      type: output_field
      field: "$.nonexistent.path"
      at: post-run
    predicate:
      type: exact-match
      expected: "something"
    on_fail: warn
on_violation:
  default: warn
""")
        contract = load_contract(p)
        runner = ContractRunner(contract)
        output = json.dumps({"other": "data"})
        result = runner.run(ctx(output=output))
        assert result.outcome_results[0].status == "failed"
        assert "Accessor error" in result.outcome_results[0].details


class TestToolResultAccessor:
    def test_exact_match_passes(self, tmp_path):
        p = write_contract(tmp_path, """
agent: test-agent
spec-version: 0.2.0
version: 1.0.0
outcomes:
  - name: ticket_closed
    accessor:
      type: tool_result
      tool: update_ticket
      field: "$.status"
      at: post-run
    predicate:
      type: exact-match
      expected: "resolved"
    on_fail: block
on_violation:
  default: block
""")
        contract = load_contract(p)
        runner = ContractRunner(contract)
        tool_calls = [{"name": "update_ticket", "result": {"status": "resolved"}}]
        result = runner.run(ctx(output="{}", tool_calls=tool_calls))
        assert result.passed
        assert result.outcome_results[0].status == "pass"

    def test_exact_match_fails(self, tmp_path):
        p = write_contract(tmp_path, """
agent: test-agent
spec-version: 0.2.0
version: 1.0.0
outcomes:
  - name: ticket_closed
    accessor:
      type: tool_result
      tool: update_ticket
      field: "$.status"
      at: post-run
    predicate:
      type: exact-match
      expected: "resolved"
    on_fail: block
on_violation:
  default: block
""")
        contract = load_contract(p)
        runner = ContractRunner(contract)
        tool_calls = [{"name": "update_ticket", "result": {"status": "open"}}]
        result = runner.run(ctx(output="{}", tool_calls=tool_calls))
        assert not result.passed
        assert result.outcome_results[0].status == "failed"

    def test_missing_tool_fails_gracefully(self, tmp_path):
        p = write_contract(tmp_path, """
agent: test-agent
spec-version: 0.2.0
version: 1.0.0
outcomes:
  - name: ticket_closed
    accessor:
      type: tool_result
      tool: update_ticket
      at: post-run
    predicate:
      type: exact-match
      expected: "resolved"
    on_fail: warn
on_violation:
  default: warn
""")
        contract = load_contract(p)
        runner = ContractRunner(contract)
        result = runner.run(ctx(output="{}"))  # no tool calls
        assert result.outcome_results[0].status == "failed"
        assert "Accessor error" in result.outcome_results[0].details

    def test_on_fail_warn_does_not_block(self, tmp_path):
        p = write_contract(tmp_path, """
agent: test-agent
spec-version: 0.2.0
version: 1.0.0
outcomes:
  - name: email_sent
    accessor:
      type: tool_result
      tool: send_email
      at: post-run
    predicate:
      type: exact-match
      expected: "ok"
    on_fail: warn
on_violation:
  default: block
""")
        contract = load_contract(p)
        runner = ContractRunner(contract)
        tool_calls = [{"name": "send_email", "result": "failed"}]
        result = runner.run(ctx(output="{}", tool_calls=tool_calls))
        assert result.passed  # warn-only
        assert result.outcome_results[0].status == "failed"
        assert any(v.action_taken == "warn" for v in result.violations)


class TestDeferredOutcome:
    def test_deferred_outcome_is_pending(self, tmp_path):
        p = write_contract(tmp_path, """
agent: test-agent
spec-version: 0.2.0
version: 1.0.0
outcomes:
  - name: email_dispatched
    accessor:
      type: tool_result
      tool: send_email
      at: deferred
      window_ms: 30000
    predicate:
      type: exact-match
      expected: "dispatched"
    on_fail: warn
on_violation:
  default: block
""")
        contract = load_contract(p)
        runner = ContractRunner(contract)
        result = runner.run(ctx(output="{}"))
        assert result.passed
        assert result.outcome_results[0].status == "pending"
        assert result.outcome == "pending"
