from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

from error import assign_or_raise, raise_if_error
from workorders import BioWorkOrder
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

  def next_requested_work_order(self) -> BioWorkOrder | None:
    # Always check for requested fragments, but only wait if biome is fully explored.
    # Note: This function assumes everything in REQUESTED_FRAGMENTS_CHANNEL is fetchable by this collector.
    result = self._comms.receive(REQUESTED_FRAGMENTS_CHANNEL)
    if result.status == "empty":
      if not self._biome_fully_explored:
        return None
      result = self._comms.wait(REQUESTED_FRAGMENTS_CHANNEL)
    # TODO: have the BioExchange include the location in the request instead of scanning.
    work_order = BioWorkOrder.from_json(assign_or_raise(result).value)
    for location in self.scan():
      if location.fragment_id == work_order.fragment:
        work_order.coords = list(location.coords)
        return work_order
    raise RuntimeError(f"{self.id!r} claimed work from {REQUESTED_FRAGMENTS_CHANNEL!r} queue, but "
                       f"the requested fragment wasn't found in scan(). Work order: {result.packet}")

  def next_exploration_work_order(self) -> BioWorkOrder | None:
    for location in self.scan():
      if not location.cataloged:
        return BioWorkOrder(coords=list(location.coords))
    self._biome_fully_explored = True
    return None

  def block_until_cargo_emptied(self) -> None:
    while self.cargo is not None:
      # Wait for a bio lab's signal that it took a fragment, then check if it was from this collector.
      broadcast: BroadcastInfo = assign_or_raise(self._comms.wait_broadcast(COLLECTED_FRAGMENTS_CHANNEL))
      if self.cargo is not None and broadcast.value == self.id:
        raise RuntimeError(f"{self.id!r} still has cargo after {broadcast.sender!r} broadcast it took it.")

  def _prepare_for_main_loop(self) -> None:
    self.block_until_cargo_emptied()

  # TODO: rename this to something less silly.
  def _do_loopy_things(self) -> None:
    work_order = self.next_requested_work_order() or self.next_exploration_work_order()
    if work_order is None:
      return  # Nothing to do; next iteration will block waiting for work.
    raise_if_error(self._value.collect(work_order.coords))
    raise_if_error(self._comms.send(COLLECTED_FRAGMENTS_CHANNEL, work_order.to_json()))
    self.block_until_cargo_emptied()

  def run(self) -> None:
    self._prepare_for_main_loop()
    while True:
      self._do_loopy_things()
      break  # TODO: delete this line when script is complete.

bio_collector = BioCollectorWrapper(self, get_component("comms"))

bio_collector.run()
