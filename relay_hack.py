# lock = self.contract.lock

def brute_force(lock):
  values = [0] * lock.tumblers
  for _ in range(lock.range):
    result = lock.intercept(values)
    if all(result):
      return values
    values = [value + int(not result[i]) for i, value in enumerate(values)]
  raise RuntimeError(f"No valid code found. Final {values=} and {result=}")

code = brute_force(self.contract.lock)
debug(f"{code=}")

transmitter = get_component("transmitter")
transmitter.connect("earth")
transmitter.transmit(self.contract.id, code)