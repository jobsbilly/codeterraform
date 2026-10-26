MAX_WATTS = 10
EFFICIENCY_FLOOR = 10

def find_best_watts() -> int:
  watts = 1
  while watts <= MAX_WATTS:
    self.set_power(watts)
    efficiency = self.efficiency()
    if efficiency == 100:
      return watts
    watts += (1 if efficiency > EFFICIENCY_FLOOR else 2)
  raise RuntimeError(f"{self.id} efficiency never reached 100%")

best_watts_by_thermal_state = {}
last_known_thermal_state = None

while True:
  thermal_state = self.thermal_state()
  if thermal_state not in best_watts_by_thermal_state:
    best_watts_by_thermal_state[thermal_state] = find_best_watts()
    print(f"Found best watts for {thermal_state}: {best_watts_by_thermal_state[thermal_state]}")
  if thermal_state != last_known_thermal_state:
    self.set_power(best_watts_by_thermal_state[thermal_state])
  last_known_thermal_state = thermal_state
  
  # if thermal_state in best_watts_by_thermal_state:
  #   if thermal_state != last_known_thermal_state:
  #     self.set_power(best_watts_by_thermal_state[thermal_state])
  # else:
  #   best_watts_by_thermal_state[thermal_state] = find_best_watts()
  #   self.set_power(best_watts_by_thermal_state[thermal_state])
  #   print(f"Found best watts for {thermal_state}: {best_watts_by_thermal_state[thermal_state]}")
  # last_known_thermal_state = thermal_state