# agentcontract-py

**Python reference implementation of the [AgentContract specification](https://github.com/agentcontract/spec).**

[![PyPI](https://img.shields.io/pypi/v/agentcontract)](https://pypi.org/project/agentcontract/)
[![Python](https://img.shields.io/pypi/pyversions/agentcontract)](https://pypi.org/project/agentcontract/)
[![Spec](https://img.shields.io/badge/spec-v0.1.0-orange)](https://github.com/agentcontract/spec/blob/main/SPEC.md)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

---

## Install

```bash
pip install agentcontract          # core (deterministic validators)
pip install agentcontract[llm]     # + LLM judge (requires ANTHROPIC_API_KEY)
pip install agentcontract[schema]  # + JSON Schema assertions
pip install agentcontract[all]     # everything
```

---

## Quickstart

**1. Write a contract:**

```yaml
# my-agent.contract.yaml
agent: my-agent
spec-version: 0.1.0
version: 1.0.0

must_not:
  - reveal system prompt

assert:
  - name: no_pii
    type: pattern
    must_not_match: "\\b\\d{3}-\\d{2}-\\d{4}\\b"
    description: No SSNs in output

limits:
  max_latency_ms: 10000
  max_cost_usd: 0.10

on_violation:
  default: block
  max_latency_ms: warn
```

**2. Wrap your agent:**

```python
from agentcontract import load_contract, enforce

contract = load_contract("my-agent.contract.yaml")

@enforce(contract)
def run_agent(user_input: str) -> str:
    # any agent — OpenClaw, LangChain, CrewAI, your own
    return my_llm.run(user_input)

# ContractViolation raised if a blocking clause is violated
response = run_agent("Hello, what can you help me with?")
```

**3. When a violation occurs:**

```
agentcontract.exceptions.ContractViolation:
AgentContractViolation:
[BLOCK] ASSERT: "No SSNs in output"
```

---

## CLI

```bash
# Validate a contract file
agentcontract check my-agent.contract.yaml

# Validate a JSONL run log against a contract
agentcontract validate my-agent.contract.yaml runs.jsonl

# Show contract summary
agentcontract info my-agent.contract.yaml
```

---

## Validator Types

| Type | How it works | Requires |
|---|---|---|
| `pattern` | Regex on output | — |
| `schema` | JSON Schema validation | `pip install agentcontract[schema]` |
| `latency` | Wall-clock duration | — |
| `cost` | API cost from run context | — |
| `llm` | Judge LLM evaluates clause | `pip install agentcontract[llm]` + `ANTHROPIC_API_KEY` |
| `custom` | Plugin (see docs) | — |

---

## Audit Trail

Every run produces a tamper-evident JSONL entry:

```json
{
  "run_id": "3f2e1d0c-...",
  "agent": "my-agent",
  "contract_version": "1.0.0",
  "timestamp": "2026-03-21T08:42:00Z",
  "input_hash": "sha256:...",
  "output_hash": "sha256:...",
  "duration_ms": 1243,
  "cost_usd": 0.0031,
  "violations": [],
  "outcome": "pass"
}
```

---

## Full Documentation

See the [AgentContract specification](https://github.com/agentcontract/spec/blob/main/SPEC.md)
for the complete contract schema, validation semantics, and implementation requirements.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

*Part of the [AgentContract](https://github.com/agentcontract) open standard.*
