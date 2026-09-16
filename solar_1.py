def best_angle(clock):
  sun_elevation = clock.get_elevation()
  return 90 - sun_elevation

_clock = get_component("clock")
while True:
  self.set_tilt(best_angle(_clock))

# for _ in range(5):
#   print(get_component("clock").real_seconds_per_hour())
#   sleep(0.3)

# hour, minute, second = get_component("clock").get_time()
# game_timestamp_seconds = second + minute * 60 + hour * 60 * 60

# debug(f"Sun Elevation:       {get_component("clock").get_elevation():2}")
# debug(f"Game time:     {hour:2}:{minute:02}:{second:02}  ({game_timestamp_seconds})")
# debug(f"Power:            {self.get_output():.02f}W")