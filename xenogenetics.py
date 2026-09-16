# print(self.contract.samples[:5])

earth_ref = set(self.contract.earth_ref)
samples = set(self.contract.samples)

alien_list = list(samples - earth_ref)

transmitter = get_component("transmitter")
transmitter.connect("earth")
transmitter.transmit(self.contract.id, alien_list)