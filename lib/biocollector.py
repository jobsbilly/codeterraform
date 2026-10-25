from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import notebook as notebooklib
import signalbus
from status import assign_or_raise, raise_if_error
from workorders import BioWorkOrder
import wrapper

class BioCollectorWrapper(wrapper.MachineWrapper):
  def __init__(self, value: BioCollector, comms: signalbus.CommsWrapper, notebook: notebooklib.NotebookWrapper):
    super().__init__(value, required=(comms, notebook))
    self._value: BioCollector
    self._comms = (comms
                   .register(BioWorkOrder.Channel.REQUESTED_FRAGMENTS, biome=self._value.outpost.biome)
                   .register(BioWorkOrder.Channel.COLLECTED_FRAGMENTS, outpost=self._value.outpost.id))
    self._notebook = notebook
    self._biome_fully_explored = False

  def next_requested_work_order(self) -> BioWorkOrder | None:
    # Always check for requested fragments, but only wait if biome is fully explored.
    # Note: This function assumes everything in the channel is fetchable by this collector.
    result = self._comms.receive(BioWorkOrder.Channel.REQUESTED_FRAGMENTS)
    if result.status == "empty":
      if not self._biome_fully_explored:
        return None
      result = self._comms.wait(BioWorkOrder.Channel.REQUESTED_FRAGMENTS)
    return BioWorkOrder.from_json(assign_or_raise(result).value)

  def next_exploration_work_order(self) -> BioWorkOrder | None:
    for location in self.scan():
      if not location.cataloged:
        return BioWorkOrder(coords=list(location.coords))
    self._biome_fully_explored = True
    print(f"BioCollectors have fully explored {self.outpost.biome!r} biome.")
    return None

  def block_until_cargo_emptied(self) -> None:
    while self.cargo is not None:
      # Wait for a BioLab's signal that it took a fragment, then check if it was from this collector.
      broadcast: BroadcastInfo = assign_or_raise(self._comms.wait_broadcast(BioWorkOrder.Channel.COLLECTED_FRAGMENTS))
      if self.cargo is not None and broadcast.value == self.id:
        raise RuntimeError(f"{self.id!r} still has cargo after {broadcast.sender!r} broadcast it took it.")

  def _prepare_for_main_loop(self) -> None:
    work_order = BioWorkOrder.get_claimed(self.id, self._notebook)
    if work_order is None:
      self.block_until_cargo_emptied()
      return
    self._main_loop_iteration(work_order)

  def _main_loop_iteration(self, existing_work_order: BioWorkOrder | None = None) -> bool:
    work_order = existing_work_order or self.next_requested_work_order() or self.next_exploration_work_order()
    if work_order is None:
      return True  # Nothing to do; next iteration will block waiting for work.

    # Persist the work order to make sure it isn't lost if the script stops mid-loop.
    raise_if_error(work_order.claim(self.id, self._notebook))

    if self.cargo is None:
      raise_if_error(self.collect(work_order.coords))

    work_order.collector = self.id
    raise_if_error(self._comms.send(BioWorkOrder.Channel.COLLECTED_FRAGMENTS, work_order.to_json()))
    # Un-persist the work order after passing it along.
    raise_if_error(work_order.release(self.id, self._notebook))

    self.block_until_cargo_emptied()

    # TODO: Shutdown (by returning False) when biome is fully explored and all orders in the biome have been completed.
    return True
