sensor = get_component("pressure_sensor")

def coerce_even(value):
  return value + (value % 2)

raw_value = sensor.get_value()
print(f"{raw_value=}")

print(sensor.stabilize(coerce_even(raw_value)).message)