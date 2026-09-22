from __builtins__ import *

from typing import Any

import wrapper

print(f"Starting up: {self.id!r}")

# TODO: Replace hardcoded channel names with pseudo-enum.
REQUESTED_FRAGMENTS_CHANNEL = "requested_fragments"
COLLECTED_FRAGMENTS_CHANNEL = "collected_fragments"

class BioCollectorWrapper(wrapper.WrapperBase):
  def __init__(self, value: BioCollector, clock: Clock, comms: Comms):
    if clock is None:
      raise TypeError("`clock` cannot be None")
    if comms is None:
      raise TypeError("`comms` cannot be None")
    super().__init__(value)
    self._value = value
    self._clock = clock
    self._cargo_filled_at: float | None = None
    if self.cargo is not None:
      self._mark_cargo_full()
    self._comms = comms
    self._biome_fully_explored = False

  def _mark_cargo_full(self) -> None:
    if self.cargo is None:
      raise RuntimeError("Cargo was not full")
    self._cargo_filled_at = float(self._clock.elapsed_game_hours())

  def collect(self, coords: list[Any]) -> None:
    if (result := self._value.collect(coords)).status != "ok":
      raise RuntimeError(result.message)
    self._mark_cargo_full()

  def game_hours_with_cargo_full(self) -> float:
    # if not self._cargo_filled_at:
    if self.cargo is None:
      return 0
    return self._clock.elapsed_game_hours() - self._cargo_filled_at

  def next_requested_work_order(self) -> dict[str, Any] | None:
    # Always check for requested fragments, but only wait if biome is fully explored.
    # Note: This function assumes everything in REQUESTED_FRAGMENTS_CHANNEL is fetchable by this collector.
    result = self._comms.receive(REQUESTED_FRAGMENTS_CHANNEL)
    if result.status == "empty":
      if not self._biome_fully_explored:
        return None
      result = self._comms.wait(REQUESTED_FRAGMENTS_CHANNEL)
    if result.status != "ok":
      raise RuntimeError(result.message)
    # TODO: have the BioExchange include the location in the request instead of scanning.
    for location in self.scan():
      if location.fragment_id == result.packet.value:
        return {
          "requester": result.packet.sender,
          "fragment": result.packet.value,
          "coords": list(location.coords)
        }
    raise RuntimeError(f"{self.id!r} claimed work from {REQUESTED_FRAGMENTS_CHANNEL!r} queue, but "
                       f"the requested fragment wasn't found in scan(). Work order: {result.packet}")

  def next_exploration_work_order(self) -> dict[str, Any] | None:
    for location in self.scan():
      if not location.cataloged:
        return {"coords": list(location.coords)}
    self._biome_fully_explored = True
    return None

  def collect_next_thing(self) -> None:
    if self.cargo is not None:
      raise RuntimeError("Cargo must be empty to collect anything")
    work_order = self.next_requested_work_order() or self.next_exploration_work_order()
    if work_order is not None:
      self.collect(work_order["coords"])
      if (result := self._comms.send(COLLECTED_FRAGMENTS_CHANNEL, work_order)).status != "ok":
        raise RuntimeError(result.message)

bio_collector = BioCollectorWrapper(self, get_component("clock"), get_component("comms"))

SECONDS_BETWEEN_CARGO_CHECKS = 1
TOO_MANY_GAME_HOURS_FOR_CARGO_UNLOADING = 2  # TODO: refine this value (currently a wild guess).

while True:
  # Check if self.cargo has stuff in it.
  if bio_collector.cargo is not None:
    wait_seconds = SECONDS_BETWEEN_CARGO_CHECKS
    game_hours_with_cargo_full = bio_collector.game_hours_with_cargo_full()
    if game_hours_with_cargo_full > TOO_MANY_GAME_HOURS_FOR_CARGO_UNLOADING:
      notify(f"{bio_collector.id!r} has been stuck with full cargo for {game_hours_with_cargo_full:.2f} game hours",
             level="warn", duration_seconds=0)
      wait_seconds += 300  # Unlikely to be fixed faster than this, and player can always restart the script early.
    sleep(wait_seconds)
    continue

  # TODO: instead (?) of all the above, wait for a broadcast from the bio lab after collecting.

  bio_collector.collect_next_thing()

  break  # TODO: delete this line when script is complete.

# print(self.outpost)

# print(f"{self.type_id=}")
#
# for fragment in self.scan():
#   print(fragment)
