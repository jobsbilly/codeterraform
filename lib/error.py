"""Project-specific Exception subclasses."""

from typing import TypeVar

_T = TypeVar("_T")


class CodeTerraformError(Exception):
  """Base exception for the project."""
  pass


def raise_if_none(value: _T | None, cls: type[Exception] = CodeTerraformError) -> _T:
  if value is None:
    raise cls("Cannot be None")
  return value
