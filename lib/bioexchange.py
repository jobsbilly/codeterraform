from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import bioorder
import error
import notebook as notebooklib
import signalbus
from status import assign_or_raise, raise_if_error
from workorders import BioWorkOrder
import wrapper

ESTIMATED_WORK_ORDER_DURATION_SECONDS = 20  # Calculation methodology was dubious at best.

class BioExchangeError(error.CodeTerraformError):
  pass

class BioExchangeWrapper(wrapper.MachineWrapper):
  def __init__(
      self,
      value: BioExchange,
      comms: signalbus.CommsWrapper,
      notebook: notebooklib.NotebookWrapper,
      journal: Journal
  ):
    super().__init__(value, required=(comms, notebook, journal))
    self._value: BioExchange
    self._comms = (comms
                   .register(BioWorkOrder.Channel.REQUESTED_FRAGMENTS, biome=self._value.outpost.biome)
                   .register(BioWorkOrder.Channel.PREPARED_SAMPLES, outpost=self._value.outpost.id))
    self._notebook = notebook
    self._journal = journal
    self._all_biome_work_assigned = False

  def _take_and_deliver_sample(self, work_order: BioWorkOrder) -> None:
    raise_if_error(self.set_order(work_order.order))

    if self.input.count() == 0:
      # The order of ids here matters - it should run from most recent in the pipeline to least recent.
      # TODO: consider consolidating work_order's id fields (e.g., collector, lab) into one "sample_location" field.
      raise_if_error(self.input.connect(work_order.luminizer or work_order.dna_sequencer or work_order.lab))
      for _ in range(5):
        if (result := self.input.take(work_order.fragment, 1, work_order.properties, "exact")).status != "busy":
          break
        sleep(0.25)
      raise_if_error(result)

    if (result := self.deliver()).status == "no_input":
      result_error = error.CodeTerraformError(result.message)
      if self.active_order().delivered[work_order.fragment] == self.active_order().requires[work_order.fragment]:
        raise BioExchangeError(f"Already delivered all {work_order.fragment} for {work_order.order}") from result_error
      raise result_error
    raise_if_error(self.deliver(), ignore=["complete"])

  def deliver_waiting_samples(self) -> None:
    while True:
      # Block if there's no other kind of work left; otherwise, just consume what's there and move on.
      if self._all_biome_work_assigned:
        result = self._comms.wait(BioWorkOrder.Channel.PREPARED_SAMPLES)
      elif (result := self._comms.receive(BioWorkOrder.Channel.PREPARED_SAMPLES)).status == "empty":
        break  # No samples waiting.
      work_order = BioWorkOrder.from_comms_message(assign_or_raise(result))

      raise_if_error(work_order.claim(self.id, self._notebook))

      self._take_and_deliver_sample(work_order)

      raise_if_error(work_order.release(self.id, self._notebook))

  def assign_work_to_collectors(self) -> bool:
    # Get the latest fragment discoveries.
    coords_by_fragment_id = {f.fragment_id: f.coords for f in self._journal.cataloged_fragments("nocturna")}

    # Check db for an existing claimed order.
    claimed_order = bioorder.get_claimed_order(self.id, coords_by_fragment_id, self._notebook)
    # If not found, find an order with work to be assigned.
    if not claimed_order:
      claimed_order = bioorder.claim_order(self.id, self._value.outpost.biome, coords_by_fragment_id, self._notebook)
    if not claimed_order:
      return False

    # Send out work assignments for discovered fragments.
    while True:
      fragment = claimed_order.next_needed_fragment()
      # Once all work assignments (for discovered fragments) have been sent, unclaim the order.
      if fragment is None:
        claimed_order.unclaim(self.id, self._notebook)
        break
      # Try to send a work assignment.
      work_order = BioWorkOrder(order=claimed_order.id, fragment=fragment.id, requester=self.id, coords=fragment.coords,
                                glow=claimed_order.target_glow, required_genes=fragment.required_genes)
      result = self._comms.send(BioWorkOrder.Channel.REQUESTED_FRAGMENTS, work_order.to_json())
      # If the channel can't accept any more work right now, try again on the next main loop.
      if result.status == "queue_full":
        break
      raise_if_error(result)
      # Mark the work assignment as no longer needed.
      claimed_order.one_less_needed(fragment.id, self.id, self._notebook)

    return True  # Work assignments were sent out (or the channel was full)

  def all_work_assigned(self) -> bool:
    return self._all_biome_work_assigned or bioorder.all_work_assigned(self.outpost.biome, self._notebook)

  def _prepare_for_main_loop(self) -> None:
    bioorder.populate_table_if_not_exists(self._value, self._journal, self._notebook)

    self._all_biome_work_assigned = bioorder.all_work_assigned(self.outpost.biome, self._notebook)

    if self._value.output.count() > 0:
      raise BioExchangeError("Output was not empty during startup.")

    work_order = BioWorkOrder.get_claimed(self.id, self._notebook)
    if work_order is not None:
      self._take_and_deliver_sample(work_order)
      raise_if_error(work_order.release(self.id, self._notebook))

    if self._value.input.count() > 0:
      raise BioExchangeError("Input was non-empty after claimed order handling during startup.")

  def _main_loop_iteration(self) -> bool:
    self.deliver_waiting_samples()

    if not self.all_work_assigned():
      if not self.assign_work_to_collectors():
        # There's no point looping more often than a BioCollector and BioLab take to handle a single work order.
        sleep(ESTIMATED_WORK_ORDER_DURATION_SECONDS)
      # If work was assigned this loop, don't bother sleeping; the assignments probably took some time.

    # TODO: Shutdown (by returning False) when all orders in the biome have been completed.
    return True
