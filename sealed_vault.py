from typing import Literal

from __builtins__ import *

Heading = Literal["north", "south", "east", "west"]

# In counter-clockwise order.
SORTED_HEADINGS = ("north", "west", "south", "east")

class MazeRunner:
  _heading_by_index = dict(enumerate(SORTED_HEADINGS))
  _index_by_heading = {v: k for k, v in _heading_by_index.items()}
  _heading_index_offset_by_direction = {"forward": 0, "left": 1, "back": 2, "right": 3}
  
  def __init__(self, vault: Vault, heading: Heading = "north"):
    self._vault = vault
    self._heading_index = self._index_by_heading[heading]

  @property
  def heading(self) -> Heading:
    return self._heading_by_index[self._heading_index]

  def _move(self, heading_index_offset) -> ActionResult[Literal["path", "wall", "exit"]]:
    heading_index = self._index_by_heading[self.heading]
    new_heading_index = (heading_index + heading_index_offset) % 4
    new_heading = self._heading_by_index[new_heading_index]
    result = self._vault.move(new_heading)
    if result.status != "wall":
      self._heading_index = new_heading_index
    return result

  def move_left(self) -> ActionResult[Literal["path", "wall", "exit"]]:
    return self._move(1)

  def move_forward(self) -> ActionResult[Literal["path", "wall", "exit"]]:
    return self._move(0)

  def move_right(self) -> ActionResult[Literal["path", "wall", "exit"]]:
    return self._move(3)

  def move_back(self) -> ActionResult[Literal["path", "wall", "exit"]]:
    return self._move(2)

def escape_maze(vault: Vault) -> str:
  runner = MazeRunner(vault, "north")
  while vault.escape().status != "ok":
    # Try to go left.
    result = runner.move_left()
    if result.status != "wall":
      continue
    # If left is blocked, go forward.
    result = runner.move_forward()
    if result.status != "wall":
      continue
    # If straight is blocked, go right.
    result = runner.move_right()
    if result.status != "wall":
      continue
    # If right is blocked, go back.
    result = runner.move_back()
  return vault.escape().key

transmitter = get_component("transmitter")
transmitter.connect("earth")
transmitter.transmit(self.contract.id, escape_maze(self.contract.vault))