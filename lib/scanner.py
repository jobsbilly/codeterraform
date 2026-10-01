from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import wrapper

class ScannerWrapper(wrapper.WrapperBase):
  def __init__(self, value: Scanner):
    super().__init__(value)
    self._value: Scanner

  def _prepare_for_main_loop(self) -> None:
    print(f"Starting up: {self.id!r}")

    raise NotImplementedError()

  def _main_loop(self) -> None:
    raise NotImplementedError()

  def run(self) -> None:
    self._prepare_for_main_loop()
    while True:
      self._main_loop()
