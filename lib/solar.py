from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

from status import raise_if_error
import wrapper


FIRST_LIGHT_GAME_HOUR = 6  # i.e., sunrise is at 6 AM.


class SolarGeneratorWrapper(wrapper.MachineWrapper):
  def __init__(self, value: SolarGenerator, clock: Clock):
    super().__init__(value, required=(clock,))
    self._value: SolarGenerator
    self._clock = clock

  def best_angle(self) -> float:
    sun_elevation = self._clock.get_elevation()
    return 90 - sun_elevation

  def real_seconds_until_first_light(self) -> float:
    hour, minute, second = self._clock.get_time()
    current_time_game_hours = hour + minute / 60 + second / 3600
    game_hours_until_first_light = (
        FIRST_LIGHT_GAME_HOUR + (0 if hour < FIRST_LIGHT_GAME_HOUR else 24) - current_time_game_hours)
    return game_hours_until_first_light * self._clock.real_seconds_per_hour() + 1

  def _prepare_for_main_loop(self) -> None:
    pass

  def _main_loop_iteration(self) -> bool:
    raise_if_error(self.set_tilt(self.best_angle()))
    if not self.get_output():
      sleep(self.real_seconds_until_first_light())
    return True
