from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

from error import CodeTerraformError, raise_if_none
import notebook as notebooklib
import shop as shoplib
import signalbus
from status import assign_or_raise, raise_if_error, retry
from workorders import BioWorkOrder
import wrapper

class BioLabWrapper(wrapper.MachineWrapper):
  def __init__(
      self,
      value: BioLab,
      comms: signalbus.CommsWrapper,
      notebook: notebooklib.NotebookWrapper,
      inventory: Inventory,
      shop: shoplib.ShopWrapper):
    super().__init__(value, required=(comms, notebook, inventory, shop))
    self._value: BioLab
    self._comms = (comms
                   .register(BioWorkOrder.Channel.COLLECTED_FRAGMENTS, outpost=self._value.outpost.id)
                   .register(BioWorkOrder.Channel.EXTRACTED_SAMPLES, outpost=self._value.outpost.id)
                   .register(BioWorkOrder.Channel.PREPARED_SAMPLES, outpost=self._value.outpost.id))
    self._notebook = notebook
    self._inventory = inventory
    self._shop = shop

    # TODO: Support non-home outposts by implementing reagent transportation logistics.
    if not value.outpost.is_home:
      raise NotImplementedError("Only BioLabs located at Nocturna Base are currently supported.")

  def _take_fragment_and_release_collector(self, collector_id: str) -> None:
    # Take the collector's fragment.
    raise_if_error(self._value.take_from({"id": collector_id}))
    # Release the collector by pinging the channel.
    # Note: if multiple collectors are listening, they'll all wake up, so they need to check their cargo before leaving.
    raise_if_error(self._comms.broadcast(BioWorkOrder.Channel.COLLECTED_FRAGMENTS, collector_id))

  def _block_until_specimen_arrives(self) -> BioWorkOrder:
    # Wait for a collector's signal to take its fragment.
    work_order = BioWorkOrder.from_comms_message(
      assign_or_raise(self._comms.wait(BioWorkOrder.Channel.COLLECTED_FRAGMENTS)))

    # Persist the work order to make sure it isn't lost if the script stops mid-loop.
    raise_if_error(work_order.claim(self.id, self._notebook))

    return work_order

  def buy_and_load_reagents(self) -> None:
    for reagent_id, required in self.specimen.recipe.items():
      if reagent_id in self.loaded_reagents:
        continue  # This reagent is already loaded (load only accepts the full required amount).
      if required > self._value.input.capacity():
        raise CodeTerraformError(f"Recipe for {self.specimen.fragment_id!r} requires {required} units of {reagent_id}, "
                                 f"but biolab input only has capacity for {self.input.capacity()}")
      needed = required - self._inventory.count(reagent_id)
      if needed > 0:
        self._shop.buy(reagent_id, needed)
      # Move the full required quantity of the reagent into the input buffer.
      raise_if_error(self._value.input.take(reagent_id, required))  # Blocks for `0.01 * required` h
      # Load the full required quantity of the reagent.
      raise_if_error(self._value.load(reagent_id, required))

  def _prepare_for_main_loop(self) -> None:
    # TODO: Support non-home outposts by implementing reagent transportation logistics.
    if (input_connection := self._value.input.connected_id()) not in ("", "inventory"):
      warn(f"{self.id!r} input was found connected to {input_connection!r} during startup.")
    raise_if_error(self._value.input.connect("inventory"))

    work_order = BioWorkOrder.get_claimed(self.id, self._notebook)
    if work_order is None:
      if self.specimen is not None:
        raise CodeTerraformError("Found a specimen without a work order during startup.")
      if self.input.count() > 0:
        raise CodeTerraformError("Found a non-empty input buffer without a work order during startup.")
      # Non-empty output buffer is OK - probably from previous work orders; bio exchange should pick up soon.
      if self.loaded_reagents:
        raise CodeTerraformError("Found loaded reagents without a work order during startup.")
      return

    if self.specimen is None:
      # Note: it's theoretically possible to reach this point if the script stopped after sample extraction but before
      # sending the ready message, but I'm guessing that timing is *very* unlikely. If the next line raises an exception
      # more than once in a blue moon, then that guess is probably wrong.
      self._take_fragment_and_release_collector(work_order.collector)

    # If a work order was already in progress, it should be safe to assume that anything in the input should be a
    # required reagent, and should be the full required amount (i.e., loading should just work).
    if input_stacks := self.input.stacks():
      raise_if_error(self._value.load(input_stacks[0].id, input_stacks[0].count))

    self._main_loop_iteration(work_order)

  def _main_loop_iteration(self, existing_work_order: BioWorkOrder | None = None) -> bool:
    work_order: BioWorkOrder = existing_work_order or self._block_until_specimen_arrives()

    if not self.specimen:
      self._take_fragment_and_release_collector(raise_if_none(work_order.collector))

    # Analyzing provides the reagent recipe for sample extraction.
    if self.specimen.stage == "collected":
      raise_if_error(self._value.analyze())  # Blocks for ~0.1 h.

    # If this specimen is from exploration, just discard it and wait for the next one.
    if not work_order.order:
      debug(f"{self.id!r} is discarding {self.specimen.fragment_id!r} from exploration work order: {work_order}")
      raise_if_error(self._value.discard())
      raise_if_error(work_order.release(self.id, self._notebook))
      return True

    # Load all recipe reagents, buying any that aren't already owned.
    self.buy_and_load_reagents()

    # Extract the sample.
    reagent_count = sum(self.loaded_reagents.values())
    busy_sleep_seconds = (0.1 + 0.05 * reagent_count) / 2
    raise_if_error(retry(self.extract, statuses=("busy",), attempts=5, wait_seconds=busy_sleep_seconds))

    # Send a message that a sample is ready.
    work_order.lab = self.id
    channel = (BioWorkOrder.Channel.EXTRACTED_SAMPLES if self._value.outpost.biome == "coastal"
               else BioWorkOrder.Channel.PREPARED_SAMPLES)
    raise_if_error(self._comms.send(channel, work_order.to_json()))

    # Un-persist the work order after passing it along.
    raise_if_error(work_order.release(self.id, self._notebook))

    # TODO: Shutdown (by returning False) when all orders in the biome have been completed.
    return True
