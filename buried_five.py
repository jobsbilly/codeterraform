"""
# Briefing

A transmission was pulled from deep in Nocturna's rock.
One wrapping layer replaces every source character with a group of exactly five characters.
Groups remain in source order and begin at the first token.
The same operation was applied repeatedly.

self.contract.layers gives the number of layers.
self.contract.transmission is the flat list of single-character strings.

# The analyzer

```
analyzer = self.contract.analyzer
print(analyzer.read(["H", "F", "J", "D", "W"]))
```

That observed group returns W directly. analyzer.read(group) requires exactly five string tokens.
A non-list argument or non-string token raises TypeError; the wrong length or an unrecognized, misaligned group raises ValueError.

Undo the documented number of layers, then transmit the recovered string.
"""

import itertools


chars = self.contract.transmission
for _ in range(self.contract.layers):
  chars = [self.contract.analyzer.read(list(batch)) for batch in itertools.batched(chars, 5, strict=True)]
message = "".join(chars)

transmitter = get_component("transmitter")
transmitter.connect("earth")
transmitter.transmit(self.contract.id, message)
