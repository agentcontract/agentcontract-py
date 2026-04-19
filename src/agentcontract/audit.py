"""Audit trail — writes tamper-evident JSONL entries for every run."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .runner import OutcomeResult, RunResult


class AuditWriter:
    """Appends run results to a JSONL audit log."""

    def __init__(self, log_path: str | Path = "agentcontract-audit.jsonl") -> None:
        self.log_path = Path(log_path)

    def write(self, result: RunResult, contract_path: str = "") -> dict:
        entry = self._build_entry(result, contract_path)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

    def write_resolution(
        self,
        run_id: str,
        resolved: list[OutcomeResult],
        final_outcome: str,
    ) -> dict:
        """Append an outcome_resolution entry for deferred outcomes."""
        entry: dict = {
            "entry_type": "outcome_resolution",
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "outcomes_resolved": [
                {
                    "name": o.name,
                    "status": o.status,
                    "predicate_type": o.predicate_type,
                    "details": o.details,
                }
                for o in resolved
            ],
            "final_outcome": final_outcome,
        }
        import os
        key = os.environ.get("AGENTCONTRACT_AUDIT_KEY", "")
        if key:
            import hmac
            payload = json.dumps(entry, sort_keys=True)
            entry["signature"] = hmac.new(
                key.encode(), payload.encode(), hashlib.sha256
            ).hexdigest()
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

    def _build_entry(self, result: RunResult, contract_path: str) -> dict:
        ctx = result.context
        input_text = ctx.input if ctx else ""
        output_text = ctx.output if ctx else ""

        entry = {
            "entry_type": "run",
            "run_id": result.run_id,
            "agent": result.agent,
            "contract": contract_path,
            "contract_version": result.contract_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_hash": hashlib.sha256(input_text.encode()).hexdigest(),
            "output_hash": hashlib.sha256(output_text.encode()).hexdigest(),
            "duration_ms": round(ctx.duration_ms, 2) if ctx else 0,
            "cost_usd": round(ctx.cost_usd, 6) if ctx else 0,
            "violations": [
                {
                    "clause_type": v.clause_type,
                    "clause_name": v.clause_name,
                    "clause_text": v.clause_text,
                    "severity": v.severity,
                    "action_taken": v.action_taken,
                    "judge": v.judge,
                    "details": v.details,
                }
                for v in result.violations
            ],
            "outcome_results": [
                {
                    "name": o.name,
                    "status": o.status,
                    "accessor_type": o.accessor_type,
                    "predicate_type": o.predicate_type,
                    "details": o.details,
                }
                for o in result.outcome_results
            ],
            "outcome": result.outcome,
        }

        import os
        key = os.environ.get("AGENTCONTRACT_AUDIT_KEY", "")
        if key:
            import hmac
            payload = json.dumps({k: v for k, v in entry.items() if k != "signature"}, sort_keys=True)
            entry["signature"] = hmac.new(
                key.encode(), payload.encode(), hashlib.sha256
            ).hexdigest()

        return entry
