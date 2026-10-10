from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

device: SlabDevice = self.contract.device

# for i in range(26):
#   print("".join(chr(65 + (ord(char) - 65 + i) % 26) if char != " " else char for char in device.slabs))

message = "WE HAVE NEVER BEEN ALONE OUT HERE"

transmitter = get_component("transmitter")
transmitter.connect("earth")
transmitter.transmit(self.contract.id, message)
