from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

from status import raise_if_error
import wrapper


class ChargingStationWrapper(wrapper.MachineWrapper):
  def __init__(self, value: ChargingStation):
    super().__init__(value)
    self._value: ChargingStation

  def _prepare_for_main_loop(self) -> None:
    pass  # Nothing to do.

  def _main_loop_iteration(self) -> bool:
    # TODO: Implement a system for requesting/dispatching rescue drones.
    for vehicle_id in self.get_docked():
      # TODO: get rid of this check once the dev gets rid of the warning for "target_reached".
      if get_component(vehicle_id).battery.level() < 1:
        raise_if_error(self.charge(vehicle_id), ignore=["queued", "charging", "target_reached"])
    sleep(1)
    return True
