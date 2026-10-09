from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import collections
from typing import Iterable

from error import CodeTerraformError, raise_if_error
import wrapper

SPORT_NAV_MODULE = "nav_module_sport"
RANGE_AFFECTING_MODULES = (
  "nav_module",
  SPORT_NAV_MODULE,
  "sonar_module",
  "sonar_module_wide",
  "sonar_module_deep",
  "drill_module",
  "drill_module_industrial",
  "drill_module_heavy",
  "constructor_module",
)

def wh_per_m(throttle: float, cargo_count: int, modules: Iterable[MountSlot]) -> float:
  heavy_module_count_by_id = collections.Counter(
    m.module_id for m in modules if m.module_id in RANGE_AFFECTING_MODULES)
  heavy_module_count = heavy_module_count_by_id.total()
  sport_nav_count = heavy_module_count_by_id[SPORT_NAV_MODULE]

  wh_per_m_before_sport_navs = (0.03 + 0.08 * heavy_module_count + 0.0004 * cargo_count) * throttle ** 0.5
  speed_multiplier = sport_nav_count + 1
  wh_multiplier = 1 + 1.25 * sport_nav_count + 0.35 * sport_nav_count ** 2

  return wh_per_m_before_sport_navs / speed_multiplier * wh_multiplier


class PioneerWrapper(wrapper.WrapperBase):
  def __init__(self, value: Pioneer):
    super().__init__(value)
    self._value: Pioneer

  def load(self, item_id: str, quantity: int = 1, source: str = "inventory") -> None:
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

  def unload_all(self, item_id: str | None = None, destination: str = "inventory") -> None:
    raise_if_error(self.output.connect(destination))
    for stack in self.cargo.stacks():
      if item_id is None or stack.id == item_id:
        raise_if_error(self.output.send(stack.id, stack.count))  # Blocks for 2.5 ticks per item.
    raise_if_error(self.output.disconnect())

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
