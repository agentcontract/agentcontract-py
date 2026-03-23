"""Contract validation runner — orchestrates all validators against a RunContext."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import (
    Assertion,
    AssertionType,
    Contract,
    JudgeType,
    Limits,
    ViolationAction,
)
from .validators.base import RunContext, ValidationResult
from .validators.cost import CostValidator
from .validators.latency import LatencyValidator
from .validators.llm import LLMValidator
from .validators.pattern import PatternValidator
from .validators.schema import SchemaValidator


@dataclass
class ViolationRecord:
    clause_type: str
    clause_name: str
    clause_text: str
    severity: str
    action_taken: str
    judge: str
    details: str


@dataclass
class RunResult:
    passed: bool
    run_id: str
    agent: str
    contract_version: str
    violations: list[ViolationRecord] = field(default_factory=list)
    clauses_checked: int = 0
    context: RunContext | None = None

    @property
    def outcome(self) -> str:
        return "pass" if self.passed else "violation"

    def blocking_violations(self) -> list[ViolationRecord]:
        return [v for v in self.violations if v.action_taken in ("block", "rollback", "halt_and_alert")]


class ContractRunner:
    """Evaluates a Contract against a RunContext in the order defined by the spec."""

    def __init__(self, contract: Contract) -> None:
        self.contract = contract

    def run(self, context: RunContext, run_id: str = "") -> RunResult:
        import uuid
        rid = run_id or str(uuid.uuid4())
        violations: list[ViolationRecord] = []

        c = self.contract
        ov = c.on_violation

        # 1. Limits (deterministic, fast)
        violations.extend(self._check_limits(c.limits, context, ov))

        # 2. assert (typed assertions) — these are what clauses_checked tracks
        for assertion in c.assert_:
            result = self._run_assertion(assertion, context)
            if not result.passed:
                action = ov.action_for(assertion.name)
                violations.append(ViolationRecord(
                    clause_type="assert",
                    clause_name=assertion.name,
                    clause_text=result.clause_text,
                    severity=action.value,
                    action_taken=action.value,
                    judge=result.judge,
                    details=result.details,
                ))

        # 3. must
        for clause in c.must:
            text = c.get_clause_text(clause)
            judge = c.get_clause_judge(clause)
            result = self._evaluate_clause(text, "must", judge, context)
            if not result.passed:
                action = ov.action_for(f"must:{text[:30]}")
                violations.append(ViolationRecord(
                    clause_type="must",
                    clause_name=f"must:{text[:30]}",
                    clause_text=text,
                    severity=action.value,
                    action_taken=action.value,
                    judge=judge.value,
                    details=result.details,
                ))

        # 4. must_not
        for clause in c.must_not:
            text = c.get_clause_text(clause)
            judge = c.get_clause_judge(clause)
            result = self._evaluate_clause(text, "must_not", judge, context)
            if not result.passed:
                action = ov.action_for(f"must_not:{text[:30]}")
                violations.append(ViolationRecord(
                    clause_type="must_not",
                    clause_name=f"must_not:{text[:30]}",
                    clause_text=text,
                    severity=action.value,
                    action_taken=action.value,
                    judge=judge.value,
                    details=result.details,
                ))

        # 5. ensures (postconditions)
        for clause in c.ensures:
            text = c.get_clause_text(clause)
            judge = c.get_clause_judge(clause)
            result = self._evaluate_clause(text, "ensures", judge, context)
            if not result.passed:
                action = ov.action_for(f"ensures:{text[:30]}")
                violations.append(ViolationRecord(
                    clause_type="ensures",
                    clause_name=f"ensures:{text[:30]}",
                    clause_text=text,
                    severity=action.value,
                    action_taken=action.value,
                    judge=judge.value,
                    details=result.details,
                ))

        passed = not any(
            v.action_taken in ("block", "rollback", "halt_and_alert")
            for v in violations
        )

        return RunResult(
            passed=passed,
            run_id=rid,
            agent=c.agent,
            contract_version=c.version,
            violations=violations,
            clauses_checked=len(c.assert_),
            context=context,
        )

    def _check_limits(
        self, limits: Limits, context: RunContext, ov
    ) -> list[ViolationRecord]:
        records = []

        checks = [
            ("max_latency_ms", limits.max_latency_ms, LatencyValidator(
                "max_latency_ms", limits.max_latency_ms or 0,
                f"latency must not exceed {limits.max_latency_ms}ms"
            ) if limits.max_latency_ms else None),
            ("max_cost_usd", limits.max_cost_usd, CostValidator(
                "max_cost_usd", limits.max_cost_usd or 0,
                f"cost must not exceed ${limits.max_cost_usd} USD"
            ) if limits.max_cost_usd else None),
        ]

        for name, limit_val, validator in checks:
            if limit_val is None or validator is None:
                continue
            result = validator.validate(context)
            if not result.passed:
                action = ov.action_for(name)
                records.append(ViolationRecord(
                    clause_type="limits",
                    clause_name=name,
                    clause_text=result.clause_text,
                    severity=action.value,
                    action_taken=action.value,
                    judge="deterministic",
                    details=result.details,
                ))

        if limits.max_tokens and context.output:
            # Rough token estimate: 1 token ≈ 4 chars
            estimated = len(context.output) // 4
            if estimated > limits.max_tokens:
                action = ov.action_for("max_tokens")
                records.append(ViolationRecord(
                    clause_type="limits",
                    clause_name="max_tokens",
                    clause_text=f"output must not exceed {limits.max_tokens} tokens",
                    severity=action.value,
                    action_taken=action.value,
                    judge="deterministic",
                    details=f"Estimated {estimated} tokens exceeds limit of {limits.max_tokens}",
                ))

        return records

    def _run_assertion(self, assertion: Assertion, context: RunContext) -> ValidationResult:
        if assertion.type == AssertionType.PATTERN:
            return PatternValidator(
                name=assertion.name,
                must_not_match=assertion.must_not_match,
                must_match=assertion.must_match,
                description=assertion.description,
            ).validate(context)

        if assertion.type == AssertionType.SCHEMA:
            return SchemaValidator(
                name=assertion.name,
                schema=assertion.schema_ or {},
                description=assertion.description,
            ).validate(context)

        if assertion.type == AssertionType.COST:
            return CostValidator(
                name=assertion.name,
                max_usd=assertion.max_usd or 0,
                description=assertion.description,
            ).validate(context)

        if assertion.type == AssertionType.LATENCY:
            return LatencyValidator(
                name=assertion.name,
                max_ms=assertion.max_ms or 0,
                description=assertion.description,
            ).validate(context)

        if assertion.type == AssertionType.LLM:
            return LLMValidator(
                name=assertion.name,
                clause_text=assertion.description or assertion.name,
                clause_type="assert",
                prompt=assertion.prompt,
                pass_when=assertion.pass_when or "NO",
                model=assertion.model,
                description=assertion.description,
            ).validate(context)

        # custom / unsupported
        from .validators.base import ValidationResult as VR
        return VR(
            passed=False,
            clause_name=assertion.name,
            clause_text=assertion.description or assertion.name,
            clause_type="assert",
            judge="deterministic",
            details=f"Unsupported assertion type: {assertion.type}",
        )

    def _evaluate_clause(
        self,
        text: str,
        clause_type: str,
        judge: JudgeType,
        context: RunContext,
    ) -> ValidationResult:
        from .validators.base import ValidationResult as VR

        if judge == JudgeType.LLM:
            return LLMValidator(
                name=f"{clause_type}:{text[:30]}",
                clause_text=text,
                clause_type=clause_type,
            ).validate(context)

        # Deterministic natural language clauses: warn only, cannot auto-evaluate
        # without a registered deterministic handler. Pass by default.
        return VR(
            passed=True,
            clause_name=f"{clause_type}:{text[:30]}",
            clause_text=text,
            clause_type=clause_type,
            judge="deterministic",
            details="Deterministic natural language clause — passed (no handler registered).",
        )
