"""AgentContract CLI — validate contracts and run logs from the command line."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from . import __spec_version__, __version__
from .loader import load_contract
from .exceptions import ContractLoadError


@click.group()
@click.version_option(version=__version__, prog_name="agentcontract")
def cli() -> None:
    """AgentContract — behavioral contracts for AI agents."""


@cli.command("check")
@click.argument("contract_file", type=click.Path(exists=True))
def check_command(contract_file: str) -> None:
    """Validate a contract file against the AgentContract schema."""
    try:
        contract = load_contract(contract_file)
        n_assertions = len(contract.assert_)
        n_limits = sum([
            1 if contract.limits.max_latency_ms else 0,
            1 if contract.limits.max_cost_usd else 0,
            1 if contract.limits.max_tokens else 0,
        ])
        click.echo(click.style(
            f"✓ Contract valid: {contract.agent} v{contract.version}", fg="green"
        ))
        click.echo(f"  {n_assertions} assertions, {n_limits} limits")
    except ContractLoadError as e:
        click.echo(click.style(f"✗ Invalid contract: {e}", fg="red"), err=True)
        sys.exit(1)


@cli.command("validate")
@click.argument("contract_file", type=click.Path(exists=True))
@click.argument("run_log", type=click.Path(exists=True))
@click.option("--format", "output_format", default="text", type=click.Choice(["text", "json"]))
def validate_command(contract_file: str, run_log: str, output_format: str) -> None:
    """
    Validate a run log against a contract.

    RUN_LOG must be a JSONL file with fields: input, output, duration_ms, cost_usd.
    """
    from .runner import ContractRunner, RunContext

    try:
        contract = load_contract(contract_file)
    except ContractLoadError as e:
        click.echo(click.style(f"✗ {e}", fg="red"), err=True)
        sys.exit(1)

    runner = ContractRunner(contract)
    results = []
    failed = 0

    with open(run_log, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as e:
                click.echo(f"  Line {i}: skipped (invalid JSON: {e})", err=True)
                continue

            ctx = RunContext(
                input=entry.get("input", ""),
                output=entry.get("output", ""),
                duration_ms=entry.get("duration_ms", 0),
                cost_usd=entry.get("cost_usd", 0),
            )
            result = runner.run(ctx)
            results.append(result)
            if not result.passed:
                failed += 1

    if output_format == "json":
        click.echo(json.dumps([{
            "run_id": r.run_id,
            "outcome": r.outcome,
            "violations": [
                {"clause_type": v.clause_type, "clause_text": v.clause_text,
                 "action_taken": v.action_taken, "details": v.details}
                for v in r.violations
            ],
        } for r in results], indent=2))
    else:
        total = len(results)
        passed = total - failed
        click.echo(f"\nAgentContract Validation Report")
        click.echo(f"Contract: {contract_file}  |  Runs: {total}  |  "
                   + click.style(f"Passed: {passed}", fg="green")
                   + "  |  "
                   + (click.style(f"Failed: {failed}", fg="red") if failed else click.style(f"Failed: {failed}", fg="green")))

        for r in results:
            if r.violations:
                click.echo(f"\n  Run {r.run_id[:8]}... — {click.style('VIOLATION', fg='red')}")
                for v in r.violations:
                    icon = "✗" if v.action_taken != "warn" else "⚠"
                    click.echo(f"    {icon} [{v.action_taken.upper()}] {v.clause_type}: \"{v.clause_text}\"")
                    if v.details:
                        click.echo(f"      {v.details}")

    sys.exit(1 if failed else 0)


@cli.command("info")
@click.argument("contract_file", type=click.Path(exists=True))
def info_command(contract_file: str) -> None:
    """Display a summary of a contract file."""
    try:
        c = load_contract(contract_file)
    except ContractLoadError as e:
        click.echo(click.style(f"✗ {e}", fg="red"), err=True)
        sys.exit(1)

    click.echo(f"\n{click.style('AgentContract', bold=True)} — {c.agent} v{c.version}")
    click.echo(f"  Spec version : {c.spec_version}")
    if c.description:
        click.echo(f"  Description  : {c.description}")
    if c.author:
        click.echo(f"  Author       : {c.author}")
    if c.tags:
        click.echo(f"  Tags         : {', '.join(c.tags)}")

    click.echo(f"\n  Clauses:")
    click.echo(f"    must         : {len(c.must)}")
    click.echo(f"    must_not     : {len(c.must_not)}")
    click.echo(f"    can          : {len(c.can)}")
    click.echo(f"    requires     : {len(c.requires)}")
    click.echo(f"    ensures      : {len(c.ensures)}")
    click.echo(f"    invariant    : {len(c.invariant)}")
    click.echo(f"    assert       : {len(c.assert_)}")

    if c.limits.model_fields_set or any([
        c.limits.max_tokens, c.limits.max_latency_ms, c.limits.max_cost_usd
    ]):
        click.echo(f"\n  Limits:")
        if c.limits.max_tokens:
            click.echo(f"    max_tokens   : {c.limits.max_tokens}")
        if c.limits.max_latency_ms:
            click.echo(f"    max_latency  : {c.limits.max_latency_ms}ms")
        if c.limits.max_cost_usd:
            click.echo(f"    max_cost     : ${c.limits.max_cost_usd}")

    click.echo(f"\n  Violation default: {c.on_violation.default.value}")
