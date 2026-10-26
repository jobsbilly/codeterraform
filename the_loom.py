"""
# The Loom

## Briefing

Earth recovered an alien loom, which braids two strings into one, and one record it produced.
The record contains two threads; one is a message.

The loom only weaves forward.
Its transformation is deterministic, with no hidden randomness, so controlled probes can reveal its behavior.
It is not simple alternation.

```
loom = self.contract.loom
print(loom.weave("abc", "xyz"))
```

A valid call returns the woven string directly.
Non-string arguments raise TypeError; either input longer than 30 characters raises ValueError.

self.contract.record is a 42-character record built from two equal-length 21-character threads with the same transformation.
It exceeds the per-input probe limit.
Recover both threads; one is carrier filler and the other is a readable message.
"""

from status import raise_if_error


woven = self.contract.loom.weave("".join(chr(ord("A") + code) for code in range(len(self.contract.record) / 2)),
                                 "".join(chr(ord("a") + code) for code in range(len(self.contract.record) / 2)))

str_len = len(self.contract.record) / 2
group_char_index_pairs = []
for char in woven:
  code = ord(char)
  starting_code = ord("a") if code >= ord("a") else ord("A")
  char_index = code - starting_code
  group_index = 0 if starting_code == ord("A") else 1
  group_char_index_pairs.append((group_index, char_index))

group_chars: tuple[list[str], ...] = ([" "] * str_len, [" "] * str_len)
for record_index, (group_index, char_index) in enumerate(group_char_index_pairs):
  group_chars[group_index][char_index] = self.contract.record[record_index]


for group in group_chars:
  transmitter = get_component("transmitter")
  transmitter.connect("earth")
  result = transmitter.transmit(self.contract.id, "".join(group))
  if result.status == "correct":
    break
raise_if_error(result, ignore=("correct",))
