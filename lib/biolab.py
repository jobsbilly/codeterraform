from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import enum
from operator import attrgetter, methodcaller

from error import CodeTerraformError, raise_if_none
import inventories
import notebook as notebooklib
import shop as shoplib
import signalbus
from status import assign_or_raise, raise_if_error, retry
from workorders import BioWorkOrder, CourierWorkOrder
import wrapper


REMOTE_STOCK_TARGET_TO_REQUIRED_RATIO = 20
MAX_REAGENT_STOCK = 50


class BioLabStatus(enum.IntEnum):
  ORDER_RECEIVED = 0
  DETERMINED_REAGENTS_NEEDED = 1
  REAGENTS_IN_HOME_INVENTORY = 2
  REAGENTS_IN_TRANSIT = 3
  REAGENTS_IN_TARGET_INVENTORY = 4


class BioLabWrapper(wrapper.MachineWrapper):
  def __init__(
      self,
      value: BioLab,
      comms: signalbus.CommsWrapper,
      notebook: notebooklib.NotebookWrapper,
      shop: shoplib.ShopWrapper):
    super().__init__(value, required=(comms, notebook, shop))
    self._value: BioLab
    self._comms = (comms
                   .register(BioWorkOrder.Channel.COLLECTED_FRAGMENTS, outpost=self._value.outpost.id)
                   .register(BioWorkOrder.Channel.EXTRACTED_SAMPLES, outpost=self._value.outpost.id)
                   .register(BioWorkOrder.Channel.PREPARED_SAMPLES, outpost=self._value.outpost.id))
    self._notebook = notebook
    self._shop = shop

    if not self.outpost.is_home:
      (self._comms
       .register(CourierWorkOrder.Channel.REQUESTS)
       .register(CourierWorkOrder.Channel.DELIVERIES, target=self.id))

  def _take_fragment_and_release_collector(self, collector_id: str) -> None:
    # Take the collector's fragment.
    raise_if_error(self._value.take_from({"id": collector_id}))
    # Release the collector by pinging the channel.
    # Note: if multiple collectors are listening, they'll all wake up, so they need to check their cargo before leaving.
    raise_if_error(self._comms.broadcast(BioWorkOrder.Channel.COLLECTED_FRAGMENTS, collector_id))

  def _block_until_specimen_arrives(self) -> BioWorkOrder:
    comms_message = assign_or_raise(self._comms.wait(BioWorkOrder.Channel.COLLECTED_FRAGMENTS))

    work_order = BioWorkOrder.from_comms_message(comms_message)
    work_order.lab = self.id
    work_order.lab_status = BioLabStatus.ORDER_RECEIVED

    # Persist the work order while working on it; if it fails, put the unmodified work order back before letting the
    # exception propagate.
    try:
      raise_if_error(work_order.claim(self.id, self._notebook))
    except Exception:
      raise_if_error(self._comms.send(BioWorkOrder.Channel.COLLECTED_FRAGMENTS, comms_message.value))
      raise

    return work_order

  # Returns None when the given inventory doesn't have enough unused capacity to fit the desired reagents.
  # Returns empty dict when the given inventory already contains at least the target stock level of all reagents in the
  # current recipe (i.e., no reagents need to be purchased).
  def _reagent_to_buy_by_id(self, inventory: inventories.InventoryWrapper) -> dict[str, int] | None:
    reagent_to_buy_by_id = {}
    for reagent_id, required in self.specimen.recipe.items():
      if reagent_id in self.loaded_reagents:
        continue  # This reagent is already loaded (load only accepts the full required amount).
      if required > self.input.capacity():
        raise CodeTerraformError(f"Recipe for {self.specimen.fragment_id!r} requires {required} units of {reagent_id}, "
                                 f"but biolab input only has capacity for {self.input.capacity()}")

      # Ignore existing stock at the home inventory - it might be spoken for by other BioLabs.
      # Try to keep a buffer stock at remote inventories so a Courier won't be required every order.
      if inventory.is_home:
        to_buy = required
      elif inventory.outpost.is_home:
        to_buy = required - inventory.count(reagent_id)
      else:
        if (to_buy := required - inventory.count(reagent_id)) > 0:
          to_buy = min(required * REMOTE_STOCK_TARGET_TO_REQUIRED_RATIO, MAX_REAGENT_STOCK)
        # stock_target = required * REMOTE_STOCK_TARGET_TO_REQUIRED_RATIO
        # to_buy = min(stock_target - inventory.count(reagent_id), MAX_REAGENT_STOCK)

      if to_buy > 0:
        reagent_to_buy_by_id[reagent_id] = to_buy

    # Make sure `inventory` has enough usable capacity for the whole order.
    slots_by_item_id = inventory.slots_by_item_id()
    for reagent_id, to_buy in reagent_to_buy_by_id.items():
      unused_capacity = int(sum(slot.unused_capacity() for slot in slots_by_item_id.get(reagent_id, [])))
      empty_slots = slots_by_item_id.get("", [])
      while to_buy > unused_capacity and empty_slots:
        unused_capacity += empty_slots.pop().capacity
      if to_buy > unused_capacity:
        return None

    return reagent_to_buy_by_id

  def _get_reagent_order(self, work_order: BioWorkOrder) -> tuple[dict[str, int], inventories.InventoryWrapper]:
    if work_order.lab_status >= BioLabStatus.DETERMINED_REAGENTS_NEEDED:
      return raise_if_none(work_order.reagent_to_buy_by_id), inventories.get(work_order.reagent_inventory)

    for inventory in sorted(inventories.local_to(self.outpost), key=methodcaller("capacity"), reverse=True):
      if (reagent_to_buy_by_id := self._reagent_to_buy_by_id(inventory)) is not None:
        work_order.reagent_inventory = inventory.id
        work_order.reagent_to_buy_by_id = reagent_to_buy_by_id
        # If nothing to buy, everything must already be in the target inventory.
        work_order.lab_status = (BioLabStatus.DETERMINED_REAGENTS_NEEDED if reagent_to_buy_by_id
                                 else BioLabStatus.REAGENTS_IN_TARGET_INVENTORY)
        raise_if_error(work_order.save(self.id, self._notebook))
        return reagent_to_buy_by_id, inventory
    raise CodeTerraformError("No local inventories had enough unused capacity for the desired reagents; stock targets "
                             "may need to be reduced")

  def _request_courier(self, work_order: BioWorkOrder, target: inventories.InventoryWrapper) -> None:
    home_inventory = inventories.home()
    courier_order = CourierWorkOrder(
      requester=self.id,
      requested_count_by_item_id=raise_if_none(work_order.reagent_to_buy_by_id),
      pickup_coords=home_inventory.outpost.coords(),
      pickup_inventory_id=home_inventory.id,
      delivery_coords=target.outpost.coords(),
      delivery_inventory_id=target.id,
    )
    work_order.lab_status = BioLabStatus.REAGENTS_IN_TRANSIT
    raise_if_error(self._comms.send(CourierWorkOrder.Channel.REQUESTS, courier_order.to_json()))
    raise_if_error(work_order.save(self.id, self._notebook))

  def _move_locally(self, work_order: BioWorkOrder, target: inventories.InventoryWrapper) -> None:
    if work_order.lab_status < BioLabStatus.REAGENTS_IN_TRANSIT:
      work_order.lab_status = BioLabStatus.REAGENTS_IN_TRANSIT
      raise_if_error(work_order.save(self.id, self._notebook))

    home_inventory = inventories.home()
    for reagent_id, count in raise_if_none(work_order.reagent_to_buy_by_id).copy().items():
      while (result := home_inventory.transfer_to(target.id, reagent_id, count)).status == "busy":
        sleep(0.25 * count)
      raise_if_error(result)
      # raise_if_error(retry_while_busy(lambda: home_inventory.transfer_to(target.id, reagent_id, count)))
      del raise_if_none(work_order.reagent_to_buy_by_id)[reagent_id]
      raise_if_error(work_order.save(self.id, self._notebook))

  def _buy_and_load_reagents(self, work_order: BioWorkOrder) -> None:
    reagent_to_buy_by_id, target_inventory = self._get_reagent_order(work_order)

    if work_order.lab_status < BioLabStatus.REAGENTS_IN_HOME_INVENTORY:
      try:
        self._shop.buy_all(reagent_to_buy_by_id)
      except shoplib.CreditSafetyError as e:
        raise CodeTerraformError("Reagent order was too expensive; stock targets may need to be reduced") from e
      work_order.lab_status = (BioLabStatus.REAGENTS_IN_TARGET_INVENTORY if target_inventory.is_home
                               else BioLabStatus.REAGENTS_IN_HOME_INVENTORY)
      raise_if_error(work_order.save(self.id, self._notebook))

    if work_order.lab_status < BioLabStatus.REAGENTS_IN_TARGET_INVENTORY:
      if target_inventory.outpost.is_home:
        self._move_locally(work_order, target_inventory)
      else:
        if work_order.lab_status < BioLabStatus.REAGENTS_IN_TRANSIT:
          self._request_courier(work_order, target_inventory)
        raise_if_error(self._comms.wait(CourierWorkOrder.Channel.DELIVERIES))
      work_order.lab_status = BioLabStatus.REAGENTS_IN_TARGET_INVENTORY
      raise_if_error(work_order.save(self.id, self._notebook))

    raise_if_error(self.input.connect(work_order.reagent_inventory))
    for reagent_id, required in self.specimen.recipe.items():
      if reagent_id not in self.loaded_reagents:
        while (result := self.input.take(reagent_id, required)).status == "busy":
          sleep(0.25)
        raise_if_error(result)
        raise_if_error(self._value.load(reagent_id, required))

  # Only let a fragment move into `output` when it can be safely disambiguated from other items.
  @wrapper.wait_until_clear(item_id_getter=attrgetter("specimen.fragment_id"), max_attempts=5)
  def _extract(self) -> None:
    reagent_count = sum(self.loaded_reagents.values())
    busy_sleep_seconds = (0.1 + 0.05 * reagent_count) / 2
    raise_if_error(retry(self.extract, statuses=("busy",), attempts=5, wait_seconds=busy_sleep_seconds))

  def _send_to_next_machine(self, work_order: BioWorkOrder) -> None:
    channel = BioWorkOrder.Channel.PREPARED_SAMPLES
    if self.outpost.biome == "coastal":
      channel = BioWorkOrder.Channel.EXTRACTED_SAMPLES
    # The DNA Sequencer should be skipped if required_genes aren't specified for this fragment.
    elif self.outpost.biome == "geothermal" and work_order.required_genes is not None:
      channel = BioWorkOrder.Channel.EXTRACTED_SAMPLES

    raise_if_error(self._comms.send(channel, work_order.to_json()))

  def _prepare_for_main_loop(self) -> None:
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

    if self.specimen is None and work_order.lab_status >= BioLabStatus.DETERMINED_REAGENTS_NEEDED:
      # If output is empty, the specimen must have been taken by the next machine; otherwise, assume the notification
      # was never sent.
      if self.output.count() > 0:
        work_order.properties = next(
          stack.properties for stack in self.output.stacks() if stack.id == work_order.fragment)
        self._send_to_next_machine(work_order)
      raise_if_error(work_order.release(self.id, self._notebook))
      return

    # If a work order was already in progress, it should be safe to assume that anything in the input should be a
    # required reagent, and should be the full required amount (i.e., loading should just work).
    for stack in self.input.stacks():
      while (result := self.load(stack.id, stack.count)).status == "busy":
        sleep(0.25 * stack.count)
      raise_if_error(result)

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
    self._buy_and_load_reagents(work_order)

    # Extract the sample.
    self._extract()
    work_order.properties = next(stack.properties for stack in self.output.stacks() if stack.id == work_order.fragment)

    # Send a message that a sample is ready.
    self._send_to_next_machine(work_order)

    # Un-persist the work order after passing it along.
    raise_if_error(work_order.release(self.id, self._notebook))

    # TODO: Shutdown (by returning False) when all orders in the biome have been completed.
    return True
