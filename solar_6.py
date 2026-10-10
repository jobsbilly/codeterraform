def best_angle(clock):
  sun_elevation = clock.get_elevation()
  return 90 - sun_elevation

_clock = get_component("clock")
while True:
  self.set_tilt(best_angle(_clock))