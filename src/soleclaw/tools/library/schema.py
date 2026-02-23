from __future__ import annotations
from typing import Any

REQUIRED_FIELDS = ["name", "description", "version", "parameters"]


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in manifest:
            errors.append(f"Missing required field: {field}")
    if "parameters" in manifest and not isinstance(manifest["parameters"], dict):
        errors.append("parameters must be a JSON Schema object")
    return errors
