# o2gen_1
CO2_INTAKE_COEFFICIENT = 0.1
MIN_WASTE_FOR_DUMP = 50
MAX_WASTE_BEFORE_PENALTY = 60

atmosphere = get_component("atmosphere")

# loop forever
while True:
  current_co2 = atmosphere.get_co2()
  intake_rate = current_co2 * CO2_INTAKE_COEFFICIENT
  # debug(f"Current CO₂: {current_co2} ppt; setting intake to {intake_rate}...")
  # debug(f"Result: {self.set_intake(intake_rate).message}")
  self.set_intake(intake_rate)
  
  current_waste = self.waste()
  if current_waste >= MIN_WASTE_FOR_DUMP:
    # debug(f"Current waste: {current_waste}; dumping...")
    # debug(f"Result: {self.dump_waste().message}")
    self.dump_waste()
    if current_waste > MAX_WASTE_BEFORE_PENALTY:
      warn(f"{self.id} waste ({current_waste}) was too high; output until next dump reduced by {self.dump_penalty():.2%}")