from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

from operator import attrgetter

from error import CodeTerraformError, raise_if_none
import notebook as notebooklib
import signalbus
from status import assign_or_raise, raise_if_error
from workorders import BioWorkOrder
import wrapper


class DNASequencerWrapper(wrapper.MachineWrapper):
  def __init__(self, value: DnaSequencer, comms: signalbus.CommsWrapper, notebook: notebooklib.NotebookWrapper):
    super().__init__(value, required=(comms, notebook))
    self._value: DnaSequencer
    self._comms = (comms
                   .register(BioWorkOrder.Channel.EXTRACTED_SAMPLES, outpost=self._value.outpost.id)
                   .register(BioWorkOrder.Channel.PREPARED_SAMPLES, outpost=self._value.outpost.id))
    self._notebook = notebook

  def _block_until_work(self) -> BioWorkOrder:
    comms_message = assign_or_raise(self._comms.wait(BioWorkOrder.Channel.EXTRACTED_SAMPLES))

    work_order = BioWorkOrder.from_comms_message(comms_message)
    work_order.dna_sequencer = self.id

    # Persist the work order while working on it; if it fails, put the unmodified work order back before letting the
    # exception propagate.
    try:
      raise_if_error(work_order.claim(self.id, self._notebook))
    except Exception:
      raise_if_error(self._comms.send(BioWorkOrder.Channel.EXTRACTED_SAMPLES, comms_message.value))
      raise

    return work_order

  def _take_sample(self, work_order: BioWorkOrder) -> None:
    raise_if_error(self.input.connect(raise_if_none(work_order.lab)))
    # TODO: move this (and other near-identical logic) to some kind of reusable retry function or decorator.
    for _ in range(5):
      result = self.input.take(raise_if_none(work_order.fragment), 1, work_order.properties, "exact")
      if result.status != "busy":
        break
      sleep(0.25)  # Time it takes auto feeders to transfer 1 item.
    raise_if_error(result)

  def _load_sample(self, fragment_id: str) -> None:
    # TODO: move this (and other near-identical logic) to some kind of reusable retry function or decorator.
    for _ in range(5):
      if (result := self.load(fragment_id)).status != "busy":
        break
      sleep(0.25)  # Time it takes auto feeders to transfer 1 item.
    raise_if_error(result)

  @wrapper.wait_until_clear(item_id_getter=attrgetter("chamber.fragment_id"), max_attempts=5)
  def _splice(self, required_genes: list[str]) -> None:
    raise_if_error(self.splice(required_genes))

  def _prepare_for_main_loop(self) -> None:
    work_order = BioWorkOrder.get_claimed(self.id, self._notebook)
    if work_order is None:
      if self.chamber is not None:
        raise CodeTerraformError("Found a sample without a work order during startup.")
      if self.input.count() > 0:
        raise CodeTerraformError("Found a non-empty input buffer without a work order during startup.")
      return

    self._main_loop_iteration(work_order)

  def _main_loop_iteration(self, existing_work_order: BioWorkOrder | None = None) -> bool:
    work_order = self._block_until_work()

    if any(required_gene not in self.gene_catalog() for required_gene in raise_if_none(work_order.required_genes)):
      raise CodeTerraformError(f"{work_order.required_genes=} includes a gene that isn't in {self.gene_catalog()=}")

    if not self.chamber:
      if self.input.count() == 0:
        self._take_sample(work_order)
      raise_if_error(self.load(work_order.fragment))

    self._splice(raise_if_none(work_order.required_genes))
    work_order.properties = next(stack.properties for stack in self.output.stacks() if stack.id == work_order.fragment)

    raise_if_error(self._comms.send(BioWorkOrder.Channel.PREPARED_SAMPLES, work_order.to_json()))

    raise_if_error(work_order.release(self.id, self._notebook))

    # TODO: Shutdown (by returning False) when all orders in the biome have been completed.
    return True
