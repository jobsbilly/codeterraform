from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

from typing import Callable

import error
from error import assign_or_raise, raise_if_error
import notebook as notebook_
from workorders import BioWorkOrder
import wrapper

# TODO: Replace hardcoded channel names with pseudo-enum.
REQUESTED_FRAGMENTS_CHANNEL = "requested_fragments"
PREPARED_SAMPLES_CHANNEL = "prepared_samples"

CLAIMED_ORDERS_KEY = "claimed_order_ids"

class BioExchangeError(error.CodeTerraformError):
  pass

def tx_order_claimer(
    candidate_order_ids: list[str],
    already_claimed_order_ids: set[str],
    successfully_claimed: list[str]) -> Callable[[list[str]], list[str]]:
  """Returns a function that attempts to persist a claim of responsibility for one of candidate_order_ids.

  Args:
    candidate_order_ids: A list of order IDs the caller wants to claim responsibility for. The returned function mutates
      this value in place; elements are removed as they are evaluated.
    already_claimed_order_ids: A set of order IDs that have already been claimed. The returned function may mutate this
      value in place; candidate IDs are added to it if they are found to have already been claimed.
    successfully_claimed: A list of order IDs that the returned function populates when it successfully claims a
      candidate order. At most, it will be populated with a single order ID; if no candidates are claimable, it will
      remain empty.
  """
  if successfully_claimed:
    raise ValueError("`successfully_claimed` must be an empty list.")
  def fn(claimed_order_ids: list[str]) -> list[str]:
    claimed = set(claimed_order_ids)
    while candidate_order_ids:
      candidate_id = candidate_order_ids.pop()
      if candidate_id in claimed:
        already_claimed_order_ids.add(candidate_id)
        continue
      successfully_claimed.append(candidate_id)
      claimed_order_ids.append(candidate_id)
      break
    return claimed_order_ids
  return fn

class BioExchangeWrapper(wrapper.WrapperBase):
  _claimed_order_ids: set[str] = set()

  def __init__(self, value: BioExchange, comms: Comms, notebook: notebook_.NotebookWrapper):
    if comms is None:
      raise TypeError("`comms` cannot be None")
    if notebook is None:
      raise TypeError("`notebook` cannot be None")
    super().__init__(value)
    self._value: BioExchange
    self._comms = comms
    self._notebook = notebook

    if not self._claimed_order_ids:
      self._claimed_order_ids.update(self._notebook.get(CLAIMED_ORDERS_KEY, []))

  def deliver_waiting_samples(self) -> None:
    while True:
      if (result := self._comms.receive(PREPARED_SAMPLES_CHANNEL)).status == "empty":
        break  # No samples waiting.
      work_order = BioWorkOrder.from_comms_message(assign_or_raise(result))
      # TODO: consider persisting the work order until delivery is complete.
      raise_if_error(self._value.set_order(work_order.order))
      raise_if_error(self.input.connect(work_order.lab))
      raise_if_error(self.input.take(work_order.fragment, 1))
      raise_if_error(self.deliver())

  def candidate_orders(self) -> dict[str, BioOrder]:
    """Returns all available (not active) orders for the current biome that aren't already claimed."""
    candidate_order_by_id = {}
    for order in self._value.orders():
      if order.status != "available":
        continue
      if order.biome != self._value.outpost.biome:
        continue
      if order.id in self._claimed_order_ids:
        continue
      # TODO: Figure out what to do with orders that have undiscovered fragments.
      candidate_order_by_id[order.id] = order
    return candidate_order_by_id

  def find_new_work(self) -> None:
    candidate_order_by_id = self.candidate_orders()
    if not candidate_order_by_id:
      return
    claimed_ids = []
    claimer = tx_order_claimer(list(candidate_order_by_id.keys()), self._claimed_order_ids, claimed_ids)
    raise_if_error(self._notebook.transaction(CLAIMED_ORDERS_KEY, [], claimer))
    if not claimed_ids:
      return
    # TODO: Send out work orders claimed_ids[0].

  def _prepare_for_main_loop(self) -> None:
    if self._value.output.count() > 0:
      raise BioExchangeError("Output was not empty during startup.")

    if self._value.input.count() > 0:
      print(f"{self.id!r} found something in input; attempting to deliver...")
      if not self._value.active_order():
        raise BioExchangeError("Input was non-empty with no active order during startup.")
      raise_if_error(self.deliver())

  # TODO: rename this to something less silly.
  def _do_loopy_things(self, existing_work_order: BioWorkOrder | None = None) -> None:
    # Responsibilities:
    # *   Deliver any waiting samples to the appropriate order.
    self.deliver_waiting_samples()
    # *   Find incomplete orders with viable work to do (that hasn't been requested yet) and request it.
    raise NotImplementedError()

  def run(self) -> None:
    self._prepare_for_main_loop()
    while True:
      self._do_loopy_things()
      break  # TODO: delete this line when script is complete.
