"""Project-specific Exception subclasses."""

from typing import TypeVar

_T = TypeVar("_T")


class CodeTerraformError(Exception):
  """Base exception for the project."""
  pass


def raise_if_none(value: _T | None, exc: Exception | None = None) -> _T:
  if value is None:
    raise exc or CodeTerraformError("Cannot be None")
  return value
