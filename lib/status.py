from __builtins__ import sleep

import functools
from typing import Any, Callable, Iterable

from error import CodeTerraformError

def raise_if_error(status: Any, cls: type[Exception] = CodeTerraformError, ignore: Iterable[str] = ()) -> Any:
  if status.status != "ok" and status.status not in ignore:
    raise cls(status.message)
  return status

def assign_or_raise(statusor: Any, value_name: str | None = None, cls: type[Exception] = CodeTerraformError) -> Any:
  raise_if_error(statusor, cls)
  if value_name:
    return getattr(statusor, value_name)
  values_by_name = vars(statusor)
  del values_by_name["status"]
  del values_by_name["message"]
  if len(values_by_name) == 1:
    return values_by_name.values()[0]
  return values_by_name

def retry(func: Callable[[], Any], statuses: Iterable[str], attempts: int, wait_seconds: float) -> Any:
  for _ in range(attempts):
    if (result := func()).status not in statuses:
      break
    sleep(wait_seconds)
  return result

auto_feeder_retry = functools.partial(retry, statuses=("busy",), attempts=5, wait_seconds=0.25)
