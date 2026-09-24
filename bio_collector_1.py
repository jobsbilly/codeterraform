from __builtins__ import *

from typing import Any

import wrapper

print(f"Starting up: {self.id!r}")

# TODO: Replace hardcoded channel names with pseudo-enum.
REQUESTED_FRAGMENTS_CHANNEL = "requested_fragments"
COLLECTED_FRAGMENTS_CHANNEL = "collected_fragments"

class BioCollectorWrapper(wrapper.WrapperBase):
  def __init__(self, value: BioCollector, comms: Comms):
    if comms is None:
      raise TypeError("`comms` cannot be None")
    super().__init__(value)
    self._value = value
    self._comms = comms
    self._biome_fully_explored = False

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
    work_order: dict[str, Any] = result.packet.value
    for location in self.scan():
      if location.fragment_id == work_order["fragment"]:
        return work_order |  {
          "requester": result.packet.sender,
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

  def block_until_cargo_emptied(self) -> None:
    while self.cargo is not None:
      # Wait for a bio lab's signal that it took a fragment, then check if it was from this collector.
      if (result := self._comms.wait_broadcast(COLLECTED_FRAGMENTS_CHANNEL)).status != "ok":
        raise RuntimeError(result.message)
      if self.cargo is not None and result.broadcast.value == self.id:
        raise RuntimeError(f"{self.id!r} still has cargo after {result.broadcast.sender!r} broadcast it took it.")

  def _prepare_for_main_loop(self) -> None:
    self.block_until_cargo_emptied()

  # TODO: rename this to something less silly.
  def _do_loopy_things(self) -> None:
    work_order = self.next_requested_work_order() or self.next_exploration_work_order()
    if work_order is None:
      return  # Nothing to do.
    if (result := self._value.collect(work_order["coords"])).status != "ok":
      raise RuntimeError(result.message)
    if (result := self._comms.send(COLLECTED_FRAGMENTS_CHANNEL, work_order)).status != "ok":
      raise RuntimeError(result.message)
    self.block_until_cargo_emptied()

  def run(self) -> None:
    self._prepare_for_main_loop()
    while True:
      self._do_loopy_things()
      break  # TODO: delete this line when script is complete.

bio_collector = BioCollectorWrapper(self, get_component("comms"))

bio_collector.run()
