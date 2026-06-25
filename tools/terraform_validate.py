#!/usr/bin/env python3
"""Terraform resource name validation for import tool."""
import re
from dataclasses import dataclass
from typing import List, Optional

TF_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


@dataclass
class ValidationError:
    resource_type: str
    resource_name: str
    reason: str

    def __str__(self) -> str:
        return (f"Invalid resource name: {self.resource_type}.{self.resource_name} "
                f"- {self.reason}")


def validate_resource_name(resource_type: str, resource_name: str) -> Optional[ValidationError]:
    if not resource_name:
        return ValidationError(resource_type, resource_name, "Resource name cannot be empty")
    if "-" in resource_name:
        return ValidationError(resource_type, resource_name,
            f"Hyphenated names corrupt Terraform state. Use: {resource_name.replace(chr(45), chr(95))}")
    if not TF_IDENTIFIER_PATTERN.match(resource_name):
        return ValidationError(resource_type, resource_name,
            "Must start with letter/underscore, contain only alphanumeric/underscore")
    if resource_name.startswith("__"):
        return ValidationError(resource_type, resource_name, "Double underscore prefix is reserved")
    return None


def validate_batch(resources: list) -> List[ValidationError]:
    errors = []
    for r in resources:
        err = validate_resource_name(r.get("resource_type", "unknown"), r.get("resource_name", ""))
        if err:
            errors.append(err)
    return errors


def validate_csv_import(csv_rows: list) -> List[ValidationError]:
    errors = []
    for row in csv_rows:
        name = row.get("resource_name", row.get("name", ""))
        rtype = row.get("resource_type", row.get("type", "unknown"))
        err = validate_resource_name(rtype, name)
        if err:
            errors.append(err)
    return errors
