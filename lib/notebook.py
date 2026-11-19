from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

from typing import Any, Callable, TypeVar

from status import retry_while_busy
import wrapper

_T = TypeVar("_T")

class NotebookWrapper(wrapper.WrapperBase):
  def __init__(self, value: Notebook):
    super().__init__(value)
    self._value: Notebook

  @retry_while_busy(seconds_between=0.1)
  def transaction(self, key: str, default: _T, updater: Callable[[_T], Any]):
    return self._value.transaction(key, default, updater)
