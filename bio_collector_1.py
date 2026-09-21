from __builtins__ import *

from typing import Any

import wrapper

print(f"Starting up: {self.id!r}")

# TODO: Replace hardcoded channel name with pseudo-enum.
REQUESTED_FRAGMENTS_CHANNEL = "requested_fragments"

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

  def next_order_fragment_location(self) -> FragmentLocation | None:
    if not self._comms.queue_size(REQUESTED_FRAGMENTS_CHANNEL):
      return None
    nearest_location_by_fragment_id = {}
    for found in self.scan():
      # scan() returns nearest-first, so only keep the first location for each fragment ID.
      if found.cataloged and found.fragment_id not in nearest_location_by_fragment_id:
        nearest_location_by_fragment_id[found.fragment_id] = found
    for request in self._comms.pending(REQUESTED_FRAGMENTS_CHANNEL):
      if (location := nearest_location_by_fragment_id.get(request.value, None)) is not None:
        result = self._comms.receive(REQUESTED_FRAGMENTS_CHANNEL, request.id)
        if result.status == "ok":
          return location
        if result.status == "not_found":
          # Something else claimed or cancelled this request between pending() and receive() calls.
          continue
        raise RuntimeError(result.message)
    return None

  def next_unidentified_fragment_location(self) -> FragmentLocation | None:
    for location in self.scan():
      if not location.cataloged:
        return location
    return None

  def collect_next_thing(self) -> None:
    if self.cargo is not None:
      raise RuntimeError("Cargo must be empty to collect anything")
    target_location = self.next_order_fragment_location() or self.next_unidentified_fragment_location()
    if target_location is not None:
      self.collect(list(target_location.coords))

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

  bio_collector.collect_next_thing()
  # TODO: figure out whether I should have a short sleep() here or not.
  # TODO: find some way to wait - if collected, wait for BioLab to take; otherwise, wait for new BioExchange request.

  break  # TODO: delete this line when script is complete.

# print(self.outpost)

# print(f"{self.type_id=}")
#
# for fragment in self.scan():
#   print(fragment)
