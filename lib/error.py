"""Project-specific Exception subclasses."""

from typing import TypeVar

_T = TypeVar("_T")


class CodeTerraformError(Exception):
  """Base exception for the project."""
  pass


class NoneValueError(CodeTerraformError):
  def __init__(self, message: str = "Cannot be None"):
    super().__init__(message)


def raise_if_none(value: _T | None, exc: Exception | None = None) -> _T:
  if value is None:
    raise exc or NoneValueError()
  return value
