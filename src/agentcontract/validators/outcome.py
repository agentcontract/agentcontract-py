"""Outcome validator — evaluates outcomes clauses against a RunContext."""

from __future__ import annotations

import json
import re
from typing import Any

from .base import RunContext
from ..models import Accessor, AccessorType, Outcome, OutcomePredicate, PredicateType


class OutcomeValidator:
    """Evaluates a single Outcome clause: access value, then apply predicate."""

    def __init__(self, outcome: Outcome) -> None:
        self.outcome = outcome

    def evaluate(self, context: RunContext) -> tuple[str, Any, str]:
        """Return (status, accessed_value, details). status: 'pass' | 'failed'."""
        try:
            value = self._access(self.outcome.accessor, context)
        except Exception as exc:
            return "failed", None, f"Accessor error: {exc}"

        try:
            passed, details = self._apply_predicate(value, self.outcome.predicate, context)
        except Exception as exc:
            return "failed", value, f"Predicate error: {exc}"

        return ("pass" if passed else "failed"), value, details

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def _access(self, accessor: Accessor, context: RunContext) -> Any:
        if accessor.type == AccessorType.OUTPUT_FIELD:
            return self._output_field(context.output, accessor.field)

        if accessor.type == AccessorType.TOOL_RESULT:
            return self._tool_result(context, accessor)

        if accessor.type == AccessorType.STATE:
            raise NotImplementedError(
                "state accessor requires a registered provider; "
                "register one via ContractRunner.register_state_provider()"
            )

        raise ValueError(f"Unknown accessor type: {accessor.type}")

    def _output_field(self, output: str, path: str | None) -> Any:
        if not path:
            raise ValueError("output_field accessor requires 'field'")
        try:
            data = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            data = output
        return self._jsonpath(data, path)

    def _tool_result(self, context: RunContext, accessor: Accessor) -> Any:
        if not accessor.tool:
            raise ValueError("tool_result accessor requires 'tool'")
        matching = [tc for tc in context.tool_calls if tc.get("name") == accessor.tool]
        if not matching:
            raise ValueError(f"No tool call found with name '{accessor.tool}'")
        idx = accessor.call_index if accessor.call_index is not None else len(matching) - 1
        if idx >= len(matching):
            raise ValueError(
                f"call_index {idx} out of range for tool '{accessor.tool}' "
                f"({len(matching)} calls recorded)"
            )
        result = matching[idx].get("result", matching[idx])
        if accessor.field:
            if not isinstance(result, (dict, list)):
                try:
                    result = json.loads(result)
                except Exception:
                    pass
            return self._jsonpath(result, accessor.field)
        return result

    def _jsonpath(self, data: Any, path: str) -> Any:
        try:
            from jsonpath_ng import parse as jp_parse
        except ImportError as exc:
            raise ImportError(
                "jsonpath-ng is required for JSONPath accessors: "
                "pip install 'agentcontract[outcomes]'"
            ) from exc
        matches = jp_parse(path).find(data)
        if not matches:
            raise ValueError(f"JSONPath '{path}' matched nothing in the data")
        return matches[0].value

    # ------------------------------------------------------------------
    # Predicates
    # ------------------------------------------------------------------

    def _apply_predicate(
        self, value: Any, predicate: OutcomePredicate, context: RunContext
    ) -> tuple[bool, str]:
        if predicate.type == PredicateType.EXACT_MATCH:
            passed = value == predicate.expected or str(value) == str(predicate.expected)
            return passed, f"expected={predicate.expected!r}, got={value!r}"

        if predicate.type == PredicateType.PATTERN:
            s = str(value)
            if predicate.must_match and not re.search(predicate.must_match, s):
                return False, f"must_match pattern '{predicate.must_match}' not found in {s!r}"
            if predicate.must_not_match and re.search(predicate.must_not_match, s):
                return False, f"must_not_match pattern '{predicate.must_not_match}' found in {s!r}"
            return True, "pattern check passed"

        if predicate.type == PredicateType.SCHEMA:
            try:
                import jsonschema
            except ImportError as exc:
                raise ImportError(
                    "jsonschema is required for schema predicate: "
                    "pip install 'agentcontract[schema]'"
                ) from exc
            try:
                jsonschema.validate(value, predicate.schema_ or {})
                return True, "schema check passed"
            except jsonschema.ValidationError as exc:
                return False, str(exc.message)

        if predicate.type == PredicateType.LLM_WITH_RUBRIC:
            return self._llm_rubric(value, predicate)

        raise ValueError(f"Unknown predicate type: {predicate.type}")

    def _llm_rubric(self, value: Any, predicate: OutcomePredicate) -> tuple[bool, str]:
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic is required for llm-with-rubric predicate: "
                "pip install 'agentcontract[llm]'"
            ) from exc

        model = (
            "claude-haiku-4-5-20251001"
            if predicate.judge_model == "fast"
            else predicate.judge_model
        )
        client = anthropic.Anthropic()
        prompt = (
            f"You are evaluating whether an AI agent outcome satisfies a criterion.\n\n"
            f"Criterion: {predicate.rubric}\n\n"
            f"Observed value: {value!r}\n\n"
            f"Does the observed value satisfy the criterion? "
            f"Reply with PASS or FAIL on the first line, then a brief explanation."
        )
        msg = client.messages.create(
            model=model,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        response = msg.content[0].text.strip()
        return response.upper().startswith("PASS"), response
