
original_program = self.contract.program
program = original_program.copy()
outputs = []

print(program)

def resolve_param(param: int, mode: str) -> int:
  if mode == "0":
    return program[param]
  if mode == "1":
    return param
  raise RuntimeError(f"Unknown {mode=}")

iteration = 0
ip = 0
while (instruction := f"{program[ip]:04}") != "0099":
  iteration += 1
  opcode = instruction[2:]
  param1 = resolve_param(program[ip + 1], instruction[1])
  param2 = None if opcode == "04" else resolve_param(program[ip + 2], instruction[0])

  debug(f"{iteration:>3}: {instruction!r} {program[ip + 1]:>4} {None if param2 is None else program[ip + 2]:>4} --> {opcode} {param1:>4} {param2:>4}  ({program[-5:]})")

  if opcode == "01":
    destination_ip = program[ip + 3]
    program[destination_ip] = param1 + param2
    ip += 4
  elif opcode == "02":
    destination_ip = program[ip + 3]
    program[destination_ip] = param1 * param2
    ip += 4
  elif opcode == "04":
    outputs.append(param1)
    ip += 2
  elif opcode == "05":
    if param1 != 0:
      ip = param2
    else:
      ip += 3
  else:
    raise RuntimeError(f"Unknown {opcode=} in {instruction=} at {ip=}")

print(outputs)

message = "".join(chr(64 + value) for value in outputs)

print(message)

transmitter = get_component("transmitter")
transmitter.connect("earth")
transmitter.transmit(self.contract.id, message)
