from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

from typing import Any, Callable

import wrapper

class NotebookWrapper(wrapper.WrapperBase):
  def __init__(self, value: Notebook):
    super().__init__(value)
    self._value: Notebook

  def transaction(
      self,
      key: str,
      default: JsonValue,
      updater: Callable[..., Any],
      retry_while_busy: bool = True,
      sleep_seconds: int | float = 0.1):
    result = self._value.transaction(key, default, updater)
    while result.status == "busy" and retry_while_busy:
      sleep(sleep_seconds)
      result = self._value.transaction(key, default, updater)
    return result
