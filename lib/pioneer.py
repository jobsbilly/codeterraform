from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import collections
import math
from typing import Iterable

from error import CodeTerraformError
from status import assign_or_raise, raise_if_error
import wrapper

SPORT_NAV_MODULE_ID = "nav_module_sport"
RANGE_AFFECTING_MODULES = (
  "nav_module",
  SPORT_NAV_MODULE_ID,
  "sonar_module",
  "sonar_module_wide",
  "sonar_module_deep",
  "drill_module",
  "drill_module_industrial",
  "drill_module_heavy",
  "constructor_module",
)
PROXIMITY_RADIUS_METERS = 2
BASE_TOP_SPEED_METERS_PER_HOUR = 100

def in_proximity(coords: list[float], other_coords: list[float]) -> bool:
  return math.dist(coords, other_coords) < PROXIMITY_RADIUS_METERS

def wh_per_m(throttle: float, cargo_count: int, modules: Iterable[MountSlot]) -> float:
  heavy_module_count_by_id = collections.Counter(
    m.module_id for m in modules if m.module_id in RANGE_AFFECTING_MODULES)
  heavy_module_count = heavy_module_count_by_id.total()
  sport_nav_count = heavy_module_count_by_id[SPORT_NAV_MODULE_ID]

  wh_per_m_before_sport_navs = (0.03 + 0.08 * heavy_module_count + 0.0004 * cargo_count) * throttle ** 0.5
  speed_multiplier = sport_nav_count + 1
  wh_multiplier = 1 + 1.25 * sport_nav_count + 0.35 * sport_nav_count ** 2

  return wh_per_m_before_sport_navs / speed_multiplier * wh_multiplier

def move_cost_wh(
    coords: list[float],
    target: list[float],
    throttle: float = 1,
    cargo_count: int = 0,
    *,
    modules: Iterable[MountSlot],
) -> float:
  distance_meters = math.dist(coords, target)
  if distance_meters < PROXIMITY_RADIUS_METERS:
    return 0
  return distance_meters * wh_per_m(throttle, cargo_count, modules)




class PioneerWrapper(wrapper.MachineWrapper):
  def __init__(self, value: Pioneer, clock: Clock):
    super().__init__(value, required=(clock,))
    self._value: Pioneer
    self._clock = clock

  # TODO: move cargo-related functions into a new CargoWrapper class.
  def space_for(self, item_id: str) -> int:
    available = 0
    for rack in self.cargo.racks():
      for bin_ in rack.bins:
        if bin_.item_id and bin_.item_id != item_id:
          continue  # Bins can only contain one item_id.
        available += bin_.capacity - bin_.count
    return available

  def has_space(self, item_id: str, quantity: int) -> bool:
    return self.space_for(item_id) >= quantity

  def load(self, item_id: str, quantity: int = 1, source: str = "inventory") -> None:
    if not self.has_space(item_id, quantity):
      raise CodeTerraformError(f"Aborted; not enough space to load {quantity} {item_id}")
    raise_if_error(self.input.connect(source))
    raise_if_error(self.input.take(item_id, quantity))  # Blocks for 2.5 ticks per item (total rounded up).
    raise_if_error(self.input.disconnect())

  def unload(self, item_id: str, quantity: int = 1, destination: str = "inventory") -> None:
    quantity_in_cargo = sum(stack.count for stack in self.cargo.stacks() if stack.id == item_id)
    if quantity > quantity_in_cargo:
      raise CodeTerraformError(f"Aborted; tried to unload {quantity} {item_id!r}, but cargo only has "
                               f"{quantity_in_cargo}")
    raise_if_error(self.output.connect(destination))
    unsent_count = quantity
    for stack in self.cargo.stacks():
      if stack.id != item_id:
        continue
      send_quantity = min(stack.count, unsent_count)
      raise_if_error(self.output.send(stack.id, send_quantity))  # Blocks for 2.5 ticks per item.
      unsent_count -= send_quantity
      if unsent_count == 0:
        break
    raise_if_error(self.output.disconnect())

  def unload_all(self, item_id: str | None = None, destination: str = "inventory") -> int:
    raise_if_error(self.output.connect(destination))
    total_count = 0
    for stack in self.cargo.stacks():
      if item_id is None or stack.id == item_id:
        total_count += stack.count
        raise_if_error(self.output.send(stack.id, stack.count))  # Blocks for 2.5 ticks per item.
    raise_if_error(self.output.disconnect())
    return total_count

  def coords(self) -> list[float]:
    return list(self.nav.get_position())

  def is_at(self, target: list[float]) -> bool:
    return in_proximity(self.coords(), target)

  def get_move_cost_wh(self, target: list[float], throttle: float = 1) -> float:
    return move_cost_wh(self.coords(), target, throttle, self.cargo.count(), modules=self.modules())

  def goto(self, target: list[float], throttle: float | None = None) -> None:
    if self.is_at(target):
      debug(f"Already at {target=}.")
      return

    if not throttle:
      # Find the fastest throttle with the necessary range.
      throttle = 1
      while self.get_move_cost_wh(target, throttle) > self.battery.wh():
        throttle -= 0.05
        if throttle < 0.049:
          raise CodeTerraformError(f"{target} is unreachable at any throttle (with current loadout)")
    elif self.get_move_cost_wh(target, throttle) > self.battery.wh():
      raise CodeTerraformError(f"{target} is unreachable at {throttle=} (with current loadout)")

    raise_if_error(self.nav.set_target(*target))
    raise_if_error(self.nav.set_throttle(throttle))

    # Sleep for most of the trip (but wake up with plenty of time to brake).
    game_hours_until_arrival = (
        self.nav.get_distance_to(*target) / (BASE_TOP_SPEED_METERS_PER_HOUR * self.nav.speed_multiplier()))
    real_seconds_until_arrival = game_hours_until_arrival * self._clock.real_seconds_per_hour()
    debug(f"Estimated travel time from {list(self.nav.get_position())} to {target} is {real_seconds_until_arrival} sec")
    if real_seconds_until_arrival > 3:
      sleep(real_seconds_until_arrival - 3)

    while not in_proximity(self.coords(), target):
      pass
    raise_if_error(self.nav.brake())
    debug(f"{target=} reached.")

  def survey_sites_in_range(self) -> None:
    if not any(m.module_id.startswith("sonar_") for m in self._value.modules() if m.module_id is not None):
      warn(f"Aborted: {self.id!r} has no sonar module mounted.")
      return
    for site in assign_or_raise(self.sonar.scan(), "sites"):
      if not site.surveyed:
        print(f"Surveyed new site: {assign_or_raise(self.sonar.survey(site))}")
