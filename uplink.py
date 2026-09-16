transmitter = get_component("transmitter")
thermometer = get_component("thermometer")

print(transmitter.connect("earth").message)

current_temperature = thermometer.get_value()
print(f"current temperature: {current_temperature}")

print(transmitter.transmit("current_temperature", current_temperature).message)