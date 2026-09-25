from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import error
from error import assign_or_raise, raise_if_error
import notebook as notebook_
import shop as shop_
from workorders import BioWorkOrder, WORK_ORDERS_KEY
import wrapper

print(f"Starting up: {self.id!r}")

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

  def block_until_specimen_arrives(self) -> BioWorkOrder:
    # Wait for a collector's signal to take its fragment.
    work_order = BioWorkOrder.from_comms_message(
      assign_or_raise(self._comms.wait(COLLECTED_FRAGMENTS_CHANNEL), cls=BioLabError))

    # Persist the work order to make sure it isn't lost if the script stops.
    raise_if_error(self._notebook.transaction(WORK_ORDERS_KEY, {}, work_order.tx_setter(self.id)), cls=BioLabError)

    # Take the collector's fragment.
    raise_if_error(self._value.take_from({"id": work_order.collector}), cls=BioLabError)
    # Release the collector by pinging the channel.
    # Note: if multiple collectors are listening, they'll all wake up, so they need to check their cargo before leaving.
    raise_if_error(self._comms.broadcast(COLLECTED_FRAGMENTS_CHANNEL, work_order.collector), cls=BioLabError)
    return work_order

  def buy_and_load_reagents(self) -> None:
    for reagent_id, required in self.specimen.recipe.items():
      if required > self._value.input.capacity():
        raise BioLabError(f"Recipe for {self.specimen.fragment_id!r} requires {required} units of {reagent_id}, "
                          f"but biolab input only has capacity for {self.input.capacity()}")
      needed = required - self._inventory.count(reagent_id)
      if needed:
        self._shop.buy(reagent_id, needed)
      # Move the full required quantity of the reagent into the input buffer.
      raise_if_error(self._value.input.take(reagent_id, required), cls=BioLabError)
      # Load the full required quantity of the reagent.
      raise_if_error(self._value.load(reagent_id, required), cls=BioLabError)

  def _prepare_for_main_loop(self) -> None:
    # Make sure input is connected to inventory.
    raise NotImplementedError()

  # TODO: rename this to something less silly.
  def _do_loopy_things(self) -> None:
    work_order = self.block_until_specimen_arrives()

    # Analyze the specimen, which provides the recipe.
    raise_if_error(self._value.analyze(), cls=BioLabError)  # Blocks for ~0.1 h.

    # If this specimen is from exploration, just discard it and wait for the next one.
    if not work_order.order:
      # TODO: consider broadcasting, if it would be helpful to Bio Exchanges.
      raise_if_error(self._value.discard(), cls=BioLabError)
      return

    # Load all recipe reagents, buying any that aren't already owned.
    self.buy_and_load_reagents()

    # Extract the sample.
    raise_if_error(self._value.extract(), cls=BioLabError)  # Blocks for ~0.1 + 0.05 × units h

    # Send a message to the outpost Bio Exchange channel that a sample is ready.
    work_order.lab = self.id
    raise_if_error(self._comms.send(PREPARED_SAMPLES_CHANNEL, work_order.to_json()))

    # Un-persist the work order after passing it along.
    raise_if_error(self._notebook.transaction(WORK_ORDERS_KEY, {}, work_order.tx_deleter(self.id)), cls=BioLabError)


  def run(self) -> None:
    self._prepare_for_main_loop()
    while True:
      self._do_loopy_things()
      break  # TODO: delete this line when script is complete.


# TODO: find a way to broadcast when a new fragment_id has been analyzed.
#       Maybe fetch catalogued fragments right before each analysis?

bio_lab = BioLabWrapper(
  self,
  get_component("comms"),
  notebook_.NotebookWrapper(get_component("notebook")),
  get_component("inventory"),
  shop_.ShopWrapper(get_component("shop"), get_component("commander")))

# bio_lab.run()
