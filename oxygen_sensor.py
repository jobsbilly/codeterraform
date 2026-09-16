o2_sensor = get_component("oxygen_sensor")

CALIBRATION_FACTOR = 100

raw_value = o2_sensor.get_value()
print(f"{raw_value=}")

print(o2_sensor.calibrate(raw_value * CALIBRATION_FACTOR).message)