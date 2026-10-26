"""
# Crosstalk

## Briefing

Two signals were intercepted from the same source, on overlapping channels, Earth's cryptographers are calling it crosstalk.
Each is a long string of letters with 0s and 1s scattered through.
Neither one means anything on its own.
The message is in how they differ.

## Finding the real bits

Some of the 0s and 1s in each signal are decoys.
A bit only counts if the letters around it mirror, the stretch centred on it reads the same both ways (e.g. A B 1 B A).
A bit whose neighbours don't mirror, A B 1 C A, is noise; skip it.

```
print(self.contract.input_x)
print(self.contract.input_y)
```

`self.contract.min_length` is the mirror span a bit needs to count, 5 (two matching letters on each side; longer is fine too).

Scan each signal left to right.
The real bits, in order, give you two bit streams, one from input_x (call it x), one from input_y (call it y).
They are the same length.

## Combining the streams

Pair the streams up, x[0] with y[0], x[1] with y[1], and so on, and for each pair compute:

```
x y' + x' y
```

Also expressed as: (x AND NOT y) OR (NOT x AND y)

' means NOT, two symbols side by side means AND, and + means OR. This produces one result bit per pair.

## Decoding

Take the result bits five at a time and interpret each group as a binary whole number.
The letter mapping is 1=A through 26=Z.

## Transmit

The letters, in order, spell the message, one run-together uppercase string. Transmit that string.

```
transmitter = get_component("transmitter")
transmitter.connect("earth")
transmitter.transmit(self.contract.id, message)
```
"""

import itertools


def get_signal_bits(stream: str, min_length: int) -> list[int]:
  if len(stream) < min_length:
    raise RuntimeError(f"{len(stream)=} was less than {min_length=}")
  if not (side_len := (min_length - 1) / 2).is_integer():
    raise RuntimeError(f"{min_length=} must be an odd number")
  side_len = int(side_len)
  signal_bits = []
  for i in range(side_len, len(stream) - side_len):
    if stream[i] in {"0", "1"}:
      if stream[i - side_len:i][::-1] == stream[i + 1:i + side_len + 1]:
        signal_bits.append(int(stream[i]))
  return signal_bits


signal_bits_x = get_signal_bits(self.contract.input_x, self.contract.min_length)
signal_bits_y = get_signal_bits(self.contract.input_y, self.contract.min_length)

combined_bits = [x ^ y for x, y in zip(signal_bits_x, signal_bits_y, strict=True)]
if len(combined_bits) % 5 != 0:
  raise RuntimeError(f"{len(combined_bits)=} was not cleanly divisible by 5")

message = "".join(chr(ord("A") - 1 + int("".join(map(str, char_bits)), 2))
                  for char_bits in itertools.batched(combined_bits, 5))

transmitter = get_component("transmitter")
transmitter.connect("earth")
transmitter.transmit(self.contract.id, message)
