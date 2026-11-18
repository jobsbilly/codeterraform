from __builtins__ import sleep

import functools
from typing import Any, Callable, Iterable, TypeVar

from error import CodeTerraformError

_T = TypeVar("_T")

def raise_if_error(status: _T, cls: type[Exception] = CodeTerraformError, ignore: Iterable[str] = ()) -> _T:
  if status.status != "ok" and status.status not in ignore:
    raise cls(status.message)
  return status

def assign_or_raise(statusor: Any, value_name: str | None = None, cls: type[Exception] = CodeTerraformError):
  raise_if_error(statusor, cls)
  if value_name:
    return getattr(statusor, value_name)
  values_by_name = vars(statusor)
  del values_by_name["status"]
  del values_by_name["message"]
  if len(values_by_name) == 1:
    return values_by_name.values()[0]
  return values_by_name

# DEPRECATED
def _retry(func: Callable[[], _T], statuses: Iterable[str], attempts: int, wait_seconds: float) -> _T:
  for _ in range(attempts):
    if (result := func()).status not in statuses:
      break
    sleep(wait_seconds)
  return result

def retry(statuses: Iterable[str], *, seconds_between: float | None = None, max_attempts: int | None = None):
  def decorator(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
      attempt = 0
      while (result := func(*args, **kwargs)).status in statuses:
        if (attempt := attempt + 1) == max_attempts:
          break
        if seconds_between is not None:
          sleep(seconds_between)
      return result
    return wrapper
  return decorator

retry_while_busy = functools.partial(retry, statuses=("busy",))
