from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

from collections import deque
import dataclasses
import enum
from typing import NamedTuple, Self

import error
from error import assign_or_raise, raise_if_error
import scanner as scannerlib
import shop as shoplib
import wrapper

MOVE_TO_EMPTY_HEAT_COST = 7
MOVE_TO_ITEM_HEAT_COST = 1
COOLING_UNITS_PER_HOUR = 3

def row_column_ordinals(sector: str) -> tuple[int, int]:
  return ord(sector[0]) - 64, int(sector[1:])

def row_column_indices(sector: str) -> tuple[int, int]:
  row, column = row_column_ordinals(sector)
  return row - 1, column - 1

class GridCoords(NamedTuple):
  row: int
  column: int

  def vertical_distance(self, other: Self) -> int:
    return other.row - self.row

  def horizontal_distance(self, other: Self) -> int:
    return other.column - self.column

  def manhattan_distance(self, other: Self) -> int:
    return abs(self.vertical_distance(other)) + abs(self.horizontal_distance(other))

  def offset(self, horizontal: int = 0, vertical: int = 0) -> Self:
    return self.__class__(self.row + vertical, self.column + horizontal)

  def as_sector(self) -> str:
    return f"{chr(65 + self.row)}{self.column + 1}"


@dataclasses.dataclass
class QuadrantMixin:
  min_row: int
  max_row: int
  min_col: int
  max_col: int
  travel_direction: str

  def contains(self, sector: str) -> bool:
    row, column = row_column_ordinals(sector)
    return self.min_row <= row <= self.max_row and self.min_col <= column <= self.max_col

  def targets_grouped_by_column(self, grid: list[list[str | None]]) -> deque[deque[GridCoords]]:
    targets_grouped_by_column = deque()
    for column_index, column_values in enumerate(grid):
      if column_index + 1 < self.min_col:
        continue
      if column_index + 1 > self.max_col:
        break
      column_targets = deque()
      for row_index, item in enumerate(column_values):
        if row_index + 1 < self.min_row:
          continue
        if row_index + 1 > self.max_row:
          break
        if item is not None:
          column_targets.append(GridCoords(row_index, column_index))
      if column_targets:
        targets_grouped_by_column.append(column_targets)
    return targets_grouped_by_column


class Quadrant(QuadrantMixin, enum.Enum):
  SE = scannerlib.HEIGHT / 2 + 1, scannerlib.HEIGHT, scannerlib.WIDTH / 2 + 1, scannerlib.WIDTH, "E"
  NE = 1, scannerlib.HEIGHT / 2, scannerlib.WIDTH / 2 + 1, scannerlib.WIDTH, "W"
  NW = 1, scannerlib.HEIGHT / 2, 1, scannerlib.WIDTH / 2, "W"
  SW = scannerlib.HEIGHT / 2 + 1, scannerlib.HEIGHT, 1, scannerlib.WIDTH / 2, "E"

  @classmethod
  def from_sector(cls, sector: str) -> Self:
    for quadrant in Quadrant:
      if quadrant.contains(sector):
        return quadrant
    raise ValueError(f"{sector!r} is outside any quadrant bounds.")


class HarvesterWrapper(wrapper.WrapperBase):
  def __init__(self, value: Harvester, scanner: Scanner, shop: shoplib.ShopWrapper, clock: Clock):
    super().__init__(value)
    self._value: Harvester
    self._scanner = scanner
    self._shop = shop
    self._clock = clock

    self._quadrant = Quadrant.from_sector(self.sector)
    self._grid = self._make_grid()
    self._quadrant_targets: deque[deque[GridCoords]] | None = None

  def _make_grid(self) -> list[list[str | None]]:
    grid = [[None] * scannerlib.HEIGHT for _ in range(scannerlib.WIDTH)]
    for sector, scan in self._scanner.get_scanned().items():
      if scan.status != "ok":
        continue
      row_index, column_index = row_column_indices(sector)
      grid[column_index][row_index] = scan.id
    return grid

  @property
  def sector(self) -> str:
    return self._value.position()

  @property
  def coords(self) -> GridCoords:
    return GridCoords(*row_column_indices(self.sector))

  @property
  def quadrant(self) -> Quadrant:
    return self._quadrant

  def ordered_quadrants(self) -> list[Quadrant]:
    quadrants = list(Quadrant)
    for i, quadrant in enumerate(quadrants):
      if quadrant is self.quadrant:
        return quadrants[i:] + quadrants[:i]
    raise error.CodeTerraformError("Current quadrant not found.")

  def ordered_targets(self) -> deque[GridCoords]:
    harvester_coords = self.coords
    targets = deque()
    for quadrant in self.ordered_quadrants():
      columns = quadrant.targets_grouped_by_column(self._grid)
      while columns:
        column_targets = columns.pop() if quadrant.travel_direction == "W" else columns.popleft()
        last_target = targets[-1] if targets else harvester_coords
        # Start the next column bottom-up if the bottom target is closer than the top one.
        if last_target.manhattan_distance(column_targets[0]) > last_target.manhattan_distance(column_targets[-1]):
          column_targets.reverse()
        targets.extend(column_targets)

    while targets and harvester_coords.column < targets[0].column:
      warn(f"{self.id!r} may have missed item at {targets[0]}")
      targets.popleft()

    return targets

  def _move_to_adjacent(self, sector: str, target_has_item: bool) -> None:
    attempts = 0
    start_sector = self.sector
    while  (result := self._value.move(sector)).status != "ok":
      attempts += 1
      if result.status == "already_here":
        warn(f"{self.id!r} tried to move from {start_sector} to {sector}, but status was {result.status!r} after "
             f"{attempts} attempt(s).")
        break
      if result.status == "overheated":
        if attempts > 1:
          warn(f"{self.id!r} has been overheated for {attempts} cycles.")
        move_heat_cost = MOVE_TO_ITEM_HEAT_COST if target_has_item else MOVE_TO_EMPTY_HEAT_COST
        cooling_units_required = self.get_heat() + move_heat_cost - self.get_max_heat()
        if cooling_units_required > 0:
          cooling_seconds = cooling_units_required / COOLING_UNITS_PER_HOUR * self._clock.real_seconds_per_hour()
          sleep(cooling_seconds + 0.2)  # Add a small 2-tick buffer.
        continue
      if result.status in ("moving", "busy"):
        if attempts % 10 == 0:
          warn(f"{self.id!r} has been {result.status} for {attempts} cycles.")
          sleep(1)  # Duration is arbitrary.
        continue
      raise_if_error(result)

  def _move_to(self, target: GridCoords) -> None:
    current = self.coords
    horizontal_distance = current.horizontal_distance(target)
    vertical_distance = current.vertical_distance(target)
    for _ in range(abs(horizontal_distance)):
      move_coords = current.offset(horizontal=sign(horizontal_distance))
      self._move_to_adjacent(move_coords.as_sector(), move_coords == target)
      current = move_coords
    for _ in range(abs(vertical_distance)):
      move_coords = current.offset(vertical=sign(vertical_distance))
      self._move_to_adjacent(move_coords.as_sector(), move_coords == target)
      current = move_coords

  def _collect(self) -> str:
    attempts = 0
    while (result := self.collect()).status != "ok":
      attempts += 1
      if result.status == "overheated":
        sleep(6.25)  # This duration is mostly arbitrary.
        continue
      if result.status in ("moving", "busy", "collecting"):
        if attempts % 20 == 0:
          warn(f"{self.id!r} has been {result.status} for {attempts} cycles.")
        continue
      raise_if_error(result)
    return assign_or_raise(result, value_name="id")

  def _harvest(self, target: GridCoords) -> None:
    # Move to item.
    debug(f"Moving from {self.coords} to {target}...")
    self._move_to(target)
    # Collect item.
    debug(f"Collecting item at {self.coords}...")
    item_id = self._collect()
    # Clear item from grid
    current = self.coords
    if self._grid[current.column][current.row] != item_id:
      raise error.CodeTerraformError(
        f"Item at {current} ({self._grid[current.column][current.row]!r}) doesn't match expected {item_id!r}")
    self._grid[current.column][current.row] = None
    # Store the item
    debug(f"Storing item {item_id} in base inventory...")
    raise_if_error(self.store())
    # Sell the item
    debug(f"Selling item {item_id}...")
    raise_if_error(self._shop.sell(item_id, 1))

  def _prepare_for_main_loop(self) -> None:
    if item_id := self.get_held():
      print(f"Found {item_id!r} in cargo during startup; storing it in base inventory and selling it now...")
      raise_if_error(self.store())
      raise_if_error(self._shop.sell(item_id, 1))

  def _harvest_everything(self) -> None:
    all_targets = self.ordered_targets()
    if not all_targets:
      print("No targets to harvest.")
      return
    print(f"Found {len(all_targets)} targets to harvest.")
    for target in all_targets:
      self._harvest(target)
    print("All targets harvested")

  def run(self) -> None:
    print(f"STARTUP: {self.id!r}")
    self._prepare_for_main_loop()
    self._harvest_everything()
    print(f"SHUTDOWN: {self.id!r}")
