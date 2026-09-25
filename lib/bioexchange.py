from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import error
from error import assign_or_raise, raise_if_error
from workorders import BioWorkOrder
import wrapper

# TODO: Replace hardcoded channel names with pseudo-enum.
REQUESTED_FRAGMENTS_CHANNEL = "requested_fragments"
PREPARED_SAMPLES_CHANNEL = "prepared_samples"

class BioExchangeError(error.CodeTerraformError):
  pass

class BioExchangeWrapper(wrapper.WrapperBase):
  def __init__(self, value: BioExchange, comms: Comms):
    if comms is None:
      raise TypeError("`comms` cannot be None")
    super().__init__(value)
    self._value = value
    self._comms = comms

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
