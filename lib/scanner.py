from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import random

from error import raise_if_error
import wrapper

MAX_ROW_ORDINAL = 8
MAX_COLUMN_ORDINAL = 24
# QUADRANT_HEIGHT = int(MAX_ROW_ORDINAL / 2)

# def next_quadrant_column_sector(current_sector: str) -> str:
#   current_column = int(current_sector[1:])
#   current_row = ord(current_sector[0]) - 64
#
#   if current_row <= QUADRANT_HEIGHT and current_column > 1:
#     next_column = current_column - 1
#   elif current_row > QUADRANT_HEIGHT and current_column < MAX_COLUMN_ORDINAL:
#     next_column = current_column + 1
#   else:
#     next_column = current_column
#
#   if current_column != next_column:
#     next_row = current_row
#   elif current_row <= QUADRANT_HEIGHT:
#     next_row = current_row + QUADRANT_HEIGHT
#   else:
#     next_row = current_row - QUADRANT_HEIGHT
#
#   return f"{chr(64 + next_row)}{next_column}"
#
# def quadrant_column_sectors(sector: str) -> list[str]:
#   row_min = 1 if ord(sector[0]) - 64 <= QUADRANT_HEIGHT else QUADRANT_HEIGHT + 1
#   return [f"{chr(64 + row)}{sector[1:]}" for row in range(row_min, row_min + QUADRANT_HEIGHT)]

class ScannerWrapper(wrapper.WrapperBase):
  def __init__(self, value: Scanner):
    super().__init__(value)
    self._value: Scanner
    self._sectors: tuple[str, ...] | None = None

  @property
  def sectors(self) -> tuple[str, ...]:
    if self._sectors is None:
      row_letters = [chr(65 + i) for i in range(MAX_ROW_ORDINAL)]
      self._sectors = tuple(f"{row}{column}" for row, column in product(row_letters, range(1, MAX_COLUMN_ORDINAL + 1)))
    return self._sectors

  # def scan_harvester_next_steps(self) -> None:
  #   sector = self._initial_harvester_position
  #   sectors_to_scan = quadrant_column_sectors(sector)
  #   for _ in range(2):
  #     sector = next_quadrant_column_sector(sector)
  #     sectors_to_scan.extend(quadrant_column_sectors(sector))
  #
  #   for sector in sectors_to_scan:
  #     raise_if_error(self.scan(sector), ignore=["empty"])

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
