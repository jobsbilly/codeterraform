from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import bioorder
import error
from error import assign_or_raise, raise_if_error
import notebook as notebook_
from workorders import BioWorkOrder
import wrapper

# TODO: Replace hardcoded channel names with pseudo-enum.
REQUESTED_FRAGMENTS_CHANNEL = "requested_fragments"
PREPARED_SAMPLES_CHANNEL = "prepared_samples"

ESTIMATED_WORK_ORDER_DURATION_SECONDS = 20  # Calculation methodology was dubious at best.

class BioExchangeError(error.CodeTerraformError):
  pass

class BioExchangeWrapper(wrapper.WrapperBase):
  def __init__(self, value: BioExchange, comms: Comms, notebook: notebook_.NotebookWrapper, journal: Journal):
    if comms is None:
      raise TypeError("`comms` cannot be None")
    if notebook is None:
      raise TypeError("`notebook` cannot be None")
    if journal is None:
      raise TypeError("`journal` cannot be None")
    super().__init__(value)
    self._value: BioExchange
    self._comms = comms
    self._notebook = notebook
    self._journal = journal
    self._all_biome_work_assigned = False

  def deliver_waiting_samples(self) -> None:
    while True:
      # Block if there's no other kind of work left; otherwise, just consume what's there and move on.
      if self._all_biome_work_assigned:
        result = self._comms.wait(PREPARED_SAMPLES_CHANNEL)
      elif (result := self._comms.receive(PREPARED_SAMPLES_CHANNEL)).status == "empty":
        break  # No samples waiting.

      work_order = BioWorkOrder.from_comms_message(assign_or_raise(result))
      # TODO: consider persisting the work order until delivery is complete.
      raise_if_error(self.set_order(work_order.order))
      raise_if_error(self.input.connect(work_order.lab))
      raise_if_error(self.input.take(work_order.fragment, 1))
      raise_if_error(self.deliver())

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
      fragment_id, coords = claimed_order.next_needed_fragment()
      # Once all work assignments (for discovered fragments) have been sent, unclaim the order.
      if fragment_id is None:
        claimed_order.unclaim(self.id, self._notebook)
        break
      # Try to send a work assignment.
      work_order = BioWorkOrder(order=claimed_order.id, fragment=fragment_id, requester=self.id, coords=coords)
      result = self._comms.send(REQUESTED_FRAGMENTS_CHANNEL, work_order.to_json())
      # If the channel can't accept any more work right now, try again on the next main loop.
      if result.status == "queue_full":
        break
      raise_if_error(result)
      # Mark the work assignment as no longer needed.
      claimed_order.one_less_needed(fragment_id, self.id, self._notebook)

    return True  # Work assignments were sent out (or the channel was full)

  def all_work_assigned(self) -> bool:
    return self._all_biome_work_assigned or bioorder.all_work_assigned(self.outpost.biome, self._notebook)

  def _prepare_for_main_loop(self) -> None:
    print(f"Starting up: {self.id!r}")

    bioorder.populate_table_if_not_exists(self._value, self._journal, self._notebook)

    self._all_biome_work_assigned = bioorder.all_work_assigned(self.outpost.biome, self._notebook)

    if self._value.output.count() > 0:
      raise BioExchangeError("Output was not empty during startup.")

    if self._value.input.count() > 0:
      print(f"{self.id!r} found something in input; attempting to deliver...")
      if not self._value.active_order():
        raise BioExchangeError("Input was non-empty with no active order during startup.")
      raise_if_error(self.deliver())

  # TODO: rename this to something less silly.
  def _do_loopy_things(self) -> None:
    self.deliver_waiting_samples()

    if not self.all_work_assigned():
      if not self.assign_work_to_collectors():
        # There's no point looping more often than a BioCollector and BioLab take to handle a single work order.
        sleep(ESTIMATED_WORK_ORDER_DURATION_SECONDS)
      # If work was assigned this loop, don't bother sleeping; the assignments probably took some time.

  def run(self) -> None:
    self._prepare_for_main_loop()
    while True:
      self._do_loopy_things()
      break  # TODO: delete this line when script is complete.
