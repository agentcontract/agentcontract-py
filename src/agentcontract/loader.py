"""Contract loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .exceptions import ContractLoadError
from .models import Contract


def load_contract(path: str | Path) -> Contract:
    """Load and validate a contract from a .contract.yaml or .contract.json file."""
    path = Path(path)

    if not path.exists():
        raise ContractLoadError(f"Contract file not found: {path}")

    suffix = path.suffix.lower()
    if suffix not in (".yaml", ".yml", ".json"):
        raise ContractLoadError(
            f"Unsupported contract file format: {suffix}. Use .contract.yaml or .contract.json"
        )

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ContractLoadError(f"Cannot read contract file: {e}") from e

    try:
        if suffix == ".json":
            data: dict[str, Any] = json.loads(raw)
        else:
            data = yaml.safe_load(raw)
    except (yaml.YAMLError, json.JSONDecodeError) as e:
        raise ContractLoadError(f"Failed to parse contract file: {e}") from e

    if not isinstance(data, dict):
        raise ContractLoadError("Contract file must be a YAML/JSON object at the root level.")

    try:
        return Contract.model_validate(data)
    except ValidationError as e:
        raise ContractLoadError(f"Contract schema validation failed:\n{e}") from e
