from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import random

from error import raise_if_error
import wrapper

HEIGHT = 8
WIDTH = 24

class ScannerWrapper(wrapper.MachineWrapper):
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

  def scan_for_nonempty_sectors(self) -> int:
    nonempty_sectors = 0
    for sector in random.sample(self.sectors, k=len(self.sectors)):
      if raise_if_error(self.scan(sector), ignore=["empty"]).status == "ok":
        nonempty_sectors += 1
    return nonempty_sectors

  def _prepare_for_main_loop(self) -> None:
    pass  # Nothing to do.

  def _main_loop_iteration(self) -> bool:
    if grid_has_nonempty_sectors := (self.scan_for_nonempty_sectors() == 0):
      print("Grid is fully harvested.")
    return grid_has_nonempty_sectors
