from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import wrapper


class PioneerWrapper(wrapper.WrapperBase):
  def __init__(self, value: Pioneer):
    super().__init__(value)
    self._value: Pioneer

  def _prepare_for_main_loop(self) -> None:
    raise NotImplementedError()

  def _do_loopy_things(self) -> bool:
    raise NotImplementedError()

  def run(self) -> None:
    print(f"STARTUP: {self.id!r}")
    self._prepare_for_main_loop()
    while self._do_loopy_things():
      pass
    print(f"SHUTDOWN: {self.id!r}")
