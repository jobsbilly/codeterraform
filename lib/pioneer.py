from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import collections
from typing import Iterable

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

def wh_per_m(throttle: float, modules: Iterable[MountSlot]) -> float:
  heavy_module_count_by_id = collections.Counter(
    m.module_id for m in modules if m.module_id in RANGE_AFFECTING_MODULES)
  heavy_module_count = heavy_module_count_by_id.total()
  sport_nav_count = heavy_module_count_by_id[SPORT_NAV_MODULE]

  wh_per_m_before_sport_navs = (0.03 + 0.08 * heavy_module_count) * throttle ** 0.5
  speed_multiplier = sport_nav_count + 1
  wh_multiplier = 1 + 1.25 * sport_nav_count + 0.35 * sport_nav_count ** 2

  return wh_per_m_before_sport_navs / speed_multiplier * wh_multiplier


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
