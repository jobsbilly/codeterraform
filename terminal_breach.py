MIN_VALUE = 1
MAX_VALUE = 5

def determine_known_indices(
    terminal: AlienTerminal,
    value: int,
    initial_guess: tuple,
    initial_known_indices: tuple) -> set[int]:
  known_indices = set(initial_known_indices)
  initial_result = terminal.guess(list(initial_guess))
  for i, v in enumerate(initial_guess):
    if len(known_indices) == initial_result.correct:
      break
    if v == value:
      guess = list(initial_guess)
      guess[i] = value + (1 if value < MAX_VALUE else -1)
      result = terminal.guess(guess)
      if result.correct < initial_result.correct:
        known_indices.add(i)
  return known_indices

def get_code(terminal: AlienTerminal) -> list[int]:
  guess = [None] * terminal.length
  known_indices = set()
  # Find correct indices for all values except MAX_VALUE.
  for value in range(MIN_VALUE, MAX_VALUE):
    guess = [existing_value if i in known_indices else value for i, existing_value in enumerate(guess)]
    known_indices = determine_known_indices(terminal, value, tuple(guess), tuple(known_indices))
  # Assume the only unknown indices left are MAX_VALUE.
  code = [existing_value if i in known_indices else MAX_VALUE for i, existing_value in enumerate(guess)]
  # Double-check code.
  final_result = terminal.guess(code)
  if final_result.correct != terminal.length:
    raise RuntimeError(f"Code {code!r} is at least partially incorrect. Final result: {final_result}")
  return code

transmitter = get_component("transmitter")
transmitter.connect("earth")
transmitter.transmit(self.contract.id, get_code(self.contract.terminal))