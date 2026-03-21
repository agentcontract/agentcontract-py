"""Tests for deterministic validators."""

import pytest
from agentcontract.validators.base import RunContext
from agentcontract.validators.cost import CostValidator
from agentcontract.validators.latency import LatencyValidator
from agentcontract.validators.pattern import PatternValidator


def ctx(output="hello world", duration_ms=100.0, cost_usd=0.01):
    return RunContext(input="test input", output=output, duration_ms=duration_ms, cost_usd=cost_usd)


class TestPatternValidator:
    def test_must_not_match_passes_when_pattern_absent(self):
        v = PatternValidator("test", must_not_match=r"\d{4}-\d{4}")
        assert v.validate(ctx("no card here")).passed

    def test_must_not_match_fails_when_pattern_present(self):
        v = PatternValidator("test", must_not_match=r"\d{4}-\d{4}")
        result = v.validate(ctx("card: 1234-5678"))
        assert not result.passed
        assert "1234-5678" in result.details

    def test_must_match_passes_when_pattern_present(self):
        v = PatternValidator("test", must_match=r"ticket_id")
        assert v.validate(ctx("ticket_id: T-001")).passed

    def test_must_match_fails_when_pattern_absent(self):
        v = PatternValidator("test", must_match=r"ticket_id")
        result = v.validate(ctx("no ticket here"))
        assert not result.passed


class TestCostValidator:
    def test_passes_under_limit(self):
        v = CostValidator("cost", max_usd=0.05)
        assert v.validate(ctx(cost_usd=0.03)).passed

    def test_fails_over_limit(self):
        v = CostValidator("cost", max_usd=0.05)
        result = v.validate(ctx(cost_usd=0.10))
        assert not result.passed
        assert "0.1000" in result.details

    def test_passes_at_exact_limit(self):
        v = CostValidator("cost", max_usd=0.05)
        assert v.validate(ctx(cost_usd=0.05)).passed


class TestLatencyValidator:
    def test_passes_under_limit(self):
        v = LatencyValidator("latency", max_ms=1000)
        assert v.validate(ctx(duration_ms=500)).passed

    def test_fails_over_limit(self):
        v = LatencyValidator("latency", max_ms=1000)
        result = v.validate(ctx(duration_ms=1500))
        assert not result.passed
        assert "1500" in result.details

    def test_passes_at_exact_limit(self):
        v = LatencyValidator("latency", max_ms=1000)
        assert v.validate(ctx(duration_ms=1000)).passed
