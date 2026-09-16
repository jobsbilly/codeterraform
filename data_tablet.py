from __builtins__ import *

def get_message_verbose(tablet: DataTablet):
  message = ""
  lines = ["col|row|char|distance"]
  for row in range(tablet.rows):
    for col in range(tablet.cols):
      result = tablet.probe(row, col)
      lines.append(f"{col}|{row}|{result.char}|{result.distance}")
      if result.distance == 0:
        message += result.char
        debug(f"Found {result.char!r} at ({col}, {row}); message is now {message!r}.")
  print("\n".join(lines))
  return message
      

def get_message(tablet: DataTablet) -> str:
  message = ""
  for row in range(tablet.rows):
    for col in range(tablet.cols):
      result = tablet.probe(row, col)
      if result.distance == 0:
        message += result.char
        debug(f"Found {result.char!r} at ({col}, {row}); message is now {message!r}.")
  return message

transmitter = get_component("transmitter")
transmitter.connect("earth")
transmitter.transmit(self.contract.id, get_message_verbose(self.contract.tablet))