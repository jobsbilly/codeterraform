from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import random

from error import raise_if_error
import wrapper

HEIGHT = 8
WIDTH = 24

class ScannerWrapper(wrapper.WrapperBase):
  def __init__(self, value: Scanner):
    super().__init__(value)
    self._value: Scanner
    self._sectors: tuple[str, ...] | None = None

  @property
  def sectors(self) -> tuple[str, ...]:
    if self._sectors is None:
      row_letters = [chr(65 + i) for i in range(HEIGHT)]
      self._sectors = tuple(f"{row}{column}" for row, column in product(row_letters, range(1, WIDTH + 1)))
    return self._sectors

  def scan_all_sectors(self) -> None:
    for sector in random.sample(self.sectors, k=len(self.sectors)):
      # This `raise_if_error` is currently superfluous (since "empty" and "ok" are the only statuses), but guards
      # against potential future changes.
      raise_if_error(self.scan(sector), ignore=["empty"])

  def _prepare_for_main_loop(self) -> None:
    print(f"Starting up: {self.id!r}")

    # self.scan_harvester_next_steps()

  def _main_loop(self) -> None:
    self.scan_all_sectors()

  def run(self) -> None:
    self._prepare_for_main_loop()
    while True:
      self._main_loop()
