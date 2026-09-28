from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import error
from error import assign_or_raise, raise_if_error
import notebook as notebook_
import shop as shop_
from workorders import BioWorkOrder
import wrapper

# TODO: Replace hardcoded channel name with pseudo-enum.
COLLECTED_FRAGMENTS_CHANNEL = "collected_fragments"
PREPARED_SAMPLES_CHANNEL = "prepared_samples"

class BioLabError(error.CodeTerraformError):
  pass

class BioLabWrapper(wrapper.WrapperBase):
  def __init__(
      self,
      value: BioLab,
      comms: Comms,
      notebook: notebook_.NotebookWrapper,
      inventory: Inventory,
      shop: shop_.ShopWrapper):
    if comms is None:
      raise TypeError("`comms` cannot be None")
    if notebook is None:
      raise TypeError("`notebook` cannot be None")
    if inventory is None:
      raise TypeError("`inventory` cannot be None")
    if shop is None:
      raise TypeError("`shop` cannot be None")
    super().__init__(value)
    self._value: BioLab
    self._comms = comms
    self._notebook = notebook
    self._inventory = inventory
    self._shop = shop

    # TODO: Support non-home outposts by implementing reagent transportation logistics.
    if not value.outpost.is_home:
      raise NotImplementedError("Only BioLabs located at Nocturna Base are currently supported.")

  def _take_fragment_and_release_collector(self, collector_id: str) -> None:
    # Take the collector's fragment.
    raise_if_error(self._value.take_from({"id": collector_id}), cls=BioLabError)
    # Release the collector by pinging the channel.
    # Note: if multiple collectors are listening, they'll all wake up, so they need to check their cargo before leaving.
    raise_if_error(self._comms.broadcast(COLLECTED_FRAGMENTS_CHANNEL, collector_id), cls=BioLabError)

  def block_until_specimen_arrives(self) -> BioWorkOrder:
    # Wait for a collector's signal to take its fragment.
    work_order = BioWorkOrder.from_comms_message(
      assign_or_raise(self._comms.wait(COLLECTED_FRAGMENTS_CHANNEL), cls=BioLabError))

    # Persist the work order to make sure it isn't lost if the script stops mid-loop.
    raise_if_error(work_order.claim(self.id, self._notebook), cls=BioLabError)

    self._take_fragment_and_release_collector(work_order.collector)
    return work_order

  def buy_and_load_reagents(self) -> None:
    for reagent_id, required in self.specimen.recipe.items():
      if reagent_id in self.loaded_reagents:
        continue  # This reagent is already loaded (load only accepts the full required amount).
      if required > self._value.input.capacity():
        raise BioLabError(f"Recipe for {self.specimen.fragment_id!r} requires {required} units of {reagent_id}, "
                          f"but biolab input only has capacity for {self.input.capacity()}")
      needed = required - self._inventory.count(reagent_id)
      if needed:
        self._shop.buy(reagent_id, needed)
      # Move the full required quantity of the reagent into the input buffer.
      raise_if_error(self._value.input.take(reagent_id, required), cls=BioLabError)  # Blocks for `0.01 * required` h
      # Load the full required quantity of the reagent.
      raise_if_error(self._value.load(reagent_id, required), cls=BioLabError)

  def _prepare_for_main_loop(self) -> None:
    print(f"Starting up: {self.id!r}")

    if (input_connection := self._value.input.connected_id()) not in ("", "inventory"):
      warn(f"{self.id!r} input was found connected to {input_connection!r} during startup.")
    raise_if_error(self._value.input.connect("inventory"), cls=BioLabError)

    work_order = BioWorkOrder.get_claimed(self.id, self._notebook)
    if work_order is None:
      if self.specimen is not None:
        raise BioLabError(f"{self.id!r} found a specimen without a work order during startup.")
      if self.input.count() > 0:
        raise BioLabError(f"{self.id!r} found a non-empty input buffer without a work order during startup.")
      # Non-empty output buffer is OK - probably from previous work orders; bio exchange should pick up soon.
      if self.loaded_reagents:
        raise BioLabError(f"{self.id!r} found loaded reagents without a work order during startup.")
      return

    if self.specimen is None:
      # Note: it's theoretically possible to reach this point if the script stopped after sample extraction but before
      # sending the ready message, but I'm guessing that timing is *very* unlikely. If the next line raises an exception
      # more than once in a blue moon, then that guess is probably wrong.
      self._take_fragment_and_release_collector(work_order.collector)

    # If a work order was already in progress, it should be safe to assume that anything in the input should be a
    # required reagent, and should be the full required amount (i.e., loading should just work).
    if input_stacks := self.input.stacks():
      raise_if_error(self._value.load(input_stacks[0].id, input_stacks[0].count), cls=BioLabError)

    self._do_loopy_things(work_order)

  # TODO: rename this to something less silly.
  def _do_loopy_things(self, existing_work_order: BioWorkOrder | None = None) -> None:
    work_order: BioWorkOrder = existing_work_order or self.block_until_specimen_arrives()

    # Analyze the specimen, which provides the recipe.
    if self.specimen.stage == "collected":
      raise_if_error(self._value.analyze(), cls=BioLabError)  # Blocks for ~0.1 h.

    # If this specimen is from exploration, just discard it and wait for the next one.
    if not work_order.order:
      raise_if_error(self._value.discard(), cls=BioLabError)
      raise_if_error(work_order.release(self.id, self._notebook), cls=BioLabError)
      return

    # Load all recipe reagents, buying any that aren't already owned.
    self.buy_and_load_reagents()

    # Extract the sample.
    raise_if_error(self._value.extract(), cls=BioLabError)  # Blocks for ~0.1 + 0.05 × units h

    # Send a message to the outpost Bio Exchange channel that a sample is ready.
    work_order.lab = self.id
    raise_if_error(self._comms.send(PREPARED_SAMPLES_CHANNEL, work_order.to_json()))

    # Un-persist the work order after passing it along.
    raise_if_error(work_order.release(self.id, self._notebook), cls=BioLabError)

  def run(self) -> None:
    self._prepare_for_main_loop()
    while True:
      self._do_loopy_things()
      break  # TODO: delete this line when script is complete.
