def get_pairs_by_word(archive: Archive) -> dict[str, list[int]]:
  pairs_by_word = {}
  for row in range(archive.rows):
    for col in range(archive.cols):
      pairs_by_word.setdefault(archive.flip(row, col), []).extend([row, col])
  return pairs_by_word

pairs_by_word = get_pairs_by_word(self.contract.archive)
for key, value in pairs_by_word.items():
  debug(f"{key!r}: {value!r}")

transmitter = get_component("transmitter")
transmitter.connect("earth")
transmitter.transmit(self.contract.id, pairs_by_word.values())