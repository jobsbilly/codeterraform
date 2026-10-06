from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

from typing import NamedTuple

from error import raise_if_error

pioneer = self


# Formula for Wh/m:  (0.11 + 0.08 * <# of special modules>) * <throttle>^0.5
# Note: does not factor in cargo.  Also, unknown if weather has any effect on battery usage.


def experiment_01():
  print(f"{pioneer.nav.set_target(*(target := (0, 0)))=}")
  print(f"{pioneer.nav.set_throttle(0.5)=}")


  # for _ in range(20):
  while pioneer.nav.get_distance_to(*target) >= 2:
    print()
    print(f"Distance to target: {pioneer.nav.get_distance_to(*target)}")
    print(f"Speed: {pioneer.nav.get_speed()}")
    print(f"Battery: {pioneer.battery.wh()}/{pioneer.battery.capacity()} ({pioneer.battery.level():.2%})")

  print(f"Destination reached. Braking: {pioneer.nav.brake()}")

  # print(f"Reported for 20 iterations. braking: {pioneer.nav.brake()}")
  while pioneer.nav.get_speed() > 0:
    print(f"Distance to target: {pioneer.nav.get_distance_to(*target)}")
    print(f"Speed: {pioneer.nav.get_speed()}")
    print(f"Battery: {pioneer.battery.wh()}/{pioneer.battery.capacity()} ({pioneer.battery.level():.2%})")
  print(f"Stopped at {pioneer.nav.get_position()}")
  print(f"Distance to target: {pioneer.nav.get_distance_to(*target)}")
  print(f"Battery: {pioneer.battery.wh()}/{pioneer.battery.capacity()} ({pioneer.battery.level():.2%})")


def return_home(throttle: float, brake_tolerance_meters: float = 2, emergency_stop_battery_level: float = 0.2):
  target = (0, 0)
  start_distance = pioneer.nav.get_distance_to(*target)
  if start_distance < brake_tolerance_meters:
    warn("Already at home")
    return
  start_battery = pioneer.battery.wh()
  print("Returning home...")
  debug(f"{pioneer.nav.set_target(*target)=}")
  debug(f"{pioneer.nav.set_throttle(throttle)=}")
  while pioneer.nav.get_distance_to(*target) >= brake_tolerance_meters:
    actual_speed = pioneer.nav.get_speed()
    if pioneer.battery.level() < emergency_stop_battery_level:
      warn(f"BATTERY LOW; {pioneer.nav.brake()=}")
      if pioneer.nav.get_speed() != 0:
        raise RuntimeError("SPEED IS NOT ZERO AFTER BRAKING!")
      raise RuntimeError("Battery is too low to continue")
  debug(f"{pioneer.nav.brake()=}")
  print(f"Home reached; stopped at {pioneer.nav.get_position()}")
  print(f"{throttle}|{actual_speed}|{start_distance - pioneer.nav.get_distance_to(*target)}|{start_battery - pioneer.battery.wh()}")


class ThrottleInfo(NamedTuple):
  throttle: float
  meters_per_hour: float
  meters_traveled: float
  watt_hours_used: float


def stats_for_throttle(target: tuple[float, float], throttle: float, min_battery_level: float = 0.6) -> ThrottleInfo:
  start_distance = pioneer.nav.get_distance_to(*target)
  start_battery = pioneer.battery.wh()

  target_speed = round(100 * throttle)

  # debug(f"{pioneer.nav.set_target(*target)=}")
  raise_if_error(pioneer.nav.set_target(*target))
  debug(f"{pioneer.nav.set_throttle(throttle)=}")
  # raise_if_error(pioneer.nav.set_throttle(throttle))

  for _ in range(20):
    if not isclose((actual_speed := pioneer.nav.get_speed()), target_speed):
      warn(f"{actual_speed=} did not match {target_speed=}; {pioneer.nav.brake()=}")
      if pioneer.nav.get_speed() != 0:
        raise RuntimeError("SPEED IS NOT ZERO AFTER BRAKING!")
      raise RuntimeError("Unexpected speed")
    if pioneer.battery.level() < min_battery_level:
      warn(f"BATTERY LOW; {pioneer.nav.brake()=}")
      if pioneer.nav.get_speed() != 0:
        raise RuntimeError("SPEED IS NOT ZERO AFTER BRAKING!")
      raise RuntimeError("Battery is too low to continue")
    sleep(0.2)

  debug(f"{pioneer.nav.brake()=}")
  # raise_if_error(pioneer.nav.brake())
  if pioneer.nav.get_speed() != 0:
    raise RuntimeError("SPEED IS NOT ZERO AFTER BRAKING!")

  return ThrottleInfo(throttle,
                      actual_speed,
                      start_distance - pioneer.nav.get_distance_to(*target),
                      start_battery - pioneer.battery.wh())

def experiment_02():
  print("Starting experiment 02...")
  if not isclose(pioneer.battery.level(), 1):
    warn(f"Aborted: {pioneer.battery.level()=} needs to be fully charged before starting experiment.")
    return
  if pioneer.nav.get_distance_to(0, 0) > 2:
    warn("Aborted: experiment can only be started from home.")
    return

  target = (500, pioneer.nav.get_position().y)

  for x in range(1, 11):
    info = stats_for_throttle(target, x / 10)
    print(f"{info.throttle}|{info.meters_per_hour}|{info.meters_traveled}|{info.watt_hours_used}")

  print("experiment 02 complete.")

def test_wh_per_m():
  print("Doing a quick Wh/m test at full throttle...")
  if not isclose(pioneer.battery.level(), 1):
    warn(f"Aborted: {pioneer.battery.level()=} needs to be fully charged before starting test.")
    return
  if pioneer.nav.get_distance_to(0, 0) > 2:
    warn("Aborted: test can only be started from home.")
    return
  info = stats_for_throttle((500, pioneer.nav.get_position().y), 1)
  # print(f"{info.throttle}|{info.meters_per_hour}|{info.meters_traveled}|{info.watt_hours_used}")
  print(f"Wh/m = {info.watt_hours_used / info.meters_traveled}")
  print("Test complete.")
  return_home(1, brake_tolerance_meters=1)


# test_wh_per_m()


experiment_02()

return_home(1, brake_tolerance_meters=1)

