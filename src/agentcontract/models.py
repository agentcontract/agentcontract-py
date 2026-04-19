"""Pydantic models for the AgentContract specification."""

from __future__ import annotations

from enum import Enum
from typing import Any, Union

from pydantic import BaseModel, Field


class JudgeType(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"


class ViolationAction(str, Enum):
    WARN = "warn"
    BLOCK = "block"
    ROLLBACK = "rollback"
    HALT_AND_ALERT = "halt_and_alert"


class AssertionType(str, Enum):
    PATTERN = "pattern"
    SCHEMA = "schema"
    LLM = "llm"
    COST = "cost"
    LATENCY = "latency"
    CUSTOM = "custom"


class ClauseObject(BaseModel):
    """Explicit clause form with judge annotation."""
    text: str
    judge: JudgeType = JudgeType.DETERMINISTIC
    description: str = ""

    model_config = {"extra": "forbid"}


# A clause is either a plain string or a ClauseObject
Clause = Union[str, ClauseObject]


class PreconditionClause(BaseModel):
    """Precondition clause with on_fail policy."""
    text: str
    judge: JudgeType = JudgeType.DETERMINISTIC
    on_fail: ViolationAction = ViolationAction.BLOCK
    description: str = ""

    model_config = {"extra": "forbid"}


# A precondition is either a plain string or a PreconditionClause
Precondition = Union[str, PreconditionClause]


class Assertion(BaseModel):
    """Named, typed assertion."""
    name: str
    type: AssertionType
    description: str = ""

    # pattern
    must_not_match: str | None = None
    must_match: str | None = None

    # schema
    schema_: dict[str, Any] | None = Field(None, alias="schema")

    # llm
    prompt: str | None = None
    pass_when: str | None = None
    model: str | None = None

    # cost
    max_usd: float | None = None

    # latency
    max_ms: int | None = None

    # custom
    plugin: str | None = None

    model_config = {"extra": "allow", "populate_by_name": True}


class Limits(BaseModel):
    """Quantitative hard limits."""
    max_tokens: int | None = None
    max_input_tokens: int | None = None
    max_latency_ms: int | None = None
    max_cost_usd: float | None = None
    max_tool_calls: int | None = None
    max_steps: int | None = None

    model_config = {"extra": "forbid"}


class AccessorType(str, Enum):
    OUTPUT_FIELD = "output_field"
    TOOL_RESULT = "tool_result"
    STATE = "state"


class PredicateType(str, Enum):
    EXACT_MATCH = "exact-match"
    LLM_WITH_RUBRIC = "llm-with-rubric"
    PATTERN = "pattern"
    SCHEMA = "schema"


class Accessor(BaseModel):
    type: AccessorType
    at: str = "post-run"
    window_ms: int | None = None
    # output_field
    field: str | None = None
    # tool_result
    tool: str | None = None
    call_index: int | None = None
    # state
    query: str | None = None
    provider: str | None = None

    model_config = {"extra": "forbid"}


class OutcomePredicate(BaseModel):
    type: PredicateType
    # exact-match
    expected: Any = None
    # llm-with-rubric
    rubric: str | None = None
    judge_model: str = "fast"
    # pattern
    must_match: str | None = None
    must_not_match: str | None = None
    # schema
    schema_: dict[str, Any] | None = Field(None, alias="schema")

    model_config = {"extra": "forbid", "populate_by_name": True}


class Outcome(BaseModel):
    name: str
    description: str = ""
    accessor: Accessor
    predicate: OutcomePredicate
    on_fail: ViolationAction | None = None

    model_config = {"extra": "forbid"}


class OnViolation(BaseModel):
    """Violation handlers — default + per-assertion overrides."""
    default: ViolationAction = ViolationAction.BLOCK

    model_config = {"extra": "allow"}

    def action_for(self, assertion_name: str) -> ViolationAction:
        override = self.model_extra.get(assertion_name) if self.model_extra else None
        if override:
            return ViolationAction(override)
        return self.default


class Contract(BaseModel):
    """Root AgentContract model."""
    agent: str
    spec_version: str = Field(alias="spec-version")
    version: str
    description: str = ""
    author: str = ""
    created: str = ""
    tags: list[str] = Field(default_factory=list)
    extends: str | None = None

    must: list[Clause] = Field(default_factory=list)
    must_not: list[Clause] = Field(default_factory=list)
    can: list[str] = Field(default_factory=list)
    requires: list[Precondition] = Field(default_factory=list)
    ensures: list[Clause] = Field(default_factory=list)
    invariant: list[Clause] = Field(default_factory=list)
    assert_: list[Assertion] = Field(default_factory=list, alias="assert")
    limits: Limits = Field(default_factory=Limits)
    on_violation: OnViolation = Field(default_factory=OnViolation)
    outcomes: list[Outcome] = Field(default_factory=list)

    model_config = {"extra": "forbid", "populate_by_name": True}

    def get_clause_text(self, clause: Clause) -> str:
        return clause if isinstance(clause, str) else clause.text

    def get_clause_judge(self, clause: Clause) -> JudgeType:
        if isinstance(clause, str):
            return JudgeType.DETERMINISTIC
        return clause.judge
