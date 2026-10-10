import itertools


broadcast = self.contract.broadcast

subject = "".join(c for c in chain(*itertools.zip_longest(broadcast.freq_a, broadcast.freq_b, broadcast.freq_c)) if c is not None)

transmitter = get_component("transmitter")
transmitter.connect("earth")
transmitter.transmit(self.contract.id, subject)
