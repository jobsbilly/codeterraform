from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import dataclasses
from typing import Any

from error import CodeTerraformError, raise_if_none


@dataclasses.dataclass
class InventorySlot:
  index: int
  item_id: str
  count: int
  capacity: int
  properties: ItemProperties | None

  def unused_capacity(self) -> int:
    return self.capacity - self.count


class InventoryWrapper:
  def __init__(self, value: Any):
    if value is None:
      raise TypeError(f"{type(self)} cannot wrap None")
    self._value = value

  @property
  def id(self) -> str:
    return self._value.id

  @property
  def type_id(self) -> str:
    return self._value.type_id

  @property
  def is_home(self) -> bool:
    return False

  @property
  def outpost(self) -> OutpostRef:
    return self._value.outpost

  def slots(self) -> list[InventorySlot]:
    raise NotImplementedError()

  def slots_by_item_id(self) -> dict[str, list[InventorySlot]]:
    slots_by_item_id: dict[str, list[InventorySlot]] = {}
    for slot in self.slots():
      slots_by_item_id.setdefault(slot.item_id, []).append(slot)
    return slots_by_item_id

  def stacks(self) -> list[ItemStack]:
    return self._value.stacks()

  def count(self, item_id: str) -> int:
    return self._value.count(item_id)

  def capacity(self) -> int:
    raise NotImplementedError()

  def space_for(self, item_id: str, properties: ItemProperties | None = None) -> int:
    return self._value.space_for(item_id, properties)

  def has_space(self, item_id: str, amount: int, properties: ItemProperties | None = None) -> bool:
    return self.space_for(item_id, properties) >= amount

  def transfer_to(
      self,
      target: str,
      item_id: str,
      count: int,
      properties: ItemProperties | None = None,
      property_match: str | None = None
  ):
    return self._value.transfer_to(target, item_id, count, properties, property_match)

  def compact(self):
    return self._value.compact()


class HomeInventoryWrapper(InventoryWrapper):
  def __init__(self, value: Inventory):
    super().__init__(value)
    self._value: Inventory

  @property
  def is_home(self) -> bool:
    return True

  @property
  def outpost(self) -> OutpostRef:
    return raise_if_none(get_component("outpost_network")).home()

  def _slot_capacity(self) -> int:
    capacity_for_arbitrary_item = self._value.space_for("iron_ore") + self._value.count("iron_ore")
    compatible_slot_count = sum(1 for slot in self._value.get_slots() if slot.id in {"iron_ore", ""})
    if not (slot_capacity := capacity_for_arbitrary_item / compatible_slot_count).is_integer():
      raise CodeTerraformError(f"Calculated slot capacity was not a whole number: {slot_capacity}")
    return int(slot_capacity)

  def slots(self) -> list[InventorySlot]:
    slot_capacity = self._slot_capacity()
    return [InventorySlot(slot.slot, slot.id, slot.count, slot_capacity, slot.properties)
            for slot in self._value.get_slots()]

  def capacity(self) -> int:
    return self._value.get_size() * self._slot_capacity()


class StorageBinWrapper(InventoryWrapper):
  def __init__(self, value: StorageBin):
    super().__init__(value)
    self._value: StorageBin

  def slots(self) -> list[InventorySlot]:
    item_id = self._value.get_material()
    properties = self._value.stacks()[0].properties if item_id else None
    return [InventorySlot(0, item_id, self._value.count(item_id), self._value.get_capacity(), properties)]

  def capacity(self) -> int:
    return self._value.get_capacity()

  def space_for(self, item_id: str, properties: ItemProperties | None = None) -> int:
    if self._value.get_material() not in {"", item_id}:
      return 0
    return self._value.get_capacity() - self._value.count(item_id)

  def compact(self):
    return  # No-op for single-slot inventories.


class WarehouseWrapper(InventoryWrapper):
  def __init__(self, value: Warehouse | LargeWarehouse):
    super().__init__(value)
    self._value: Warehouse | LargeWarehouse

  def slots(self) -> list[InventorySlot]:
    return [InventorySlot(slot.index, slot.item, slot.count, slot.capacity, slot.properties)
            for slot in self._value.slots()]

  def capacity(self) -> int:
    return self._value.capacity()

  def has_space(self, item_id: str, amount: int, properties: ItemProperties | None = None) -> bool:
    return self._value.has_space(item_id, amount, properties)


HOME_INVENTORY_ID = "inventory"
INVENTORY_WRAPPER_CLASS_BY_TYPE_ID = {
  "inventory": HomeInventoryWrapper,
  "storage_bin": StorageBinWrapper,
  "warehouse": WarehouseWrapper,
  "large_warehouse": WarehouseWrapper,
}

def get(inventory_id) -> InventoryWrapper:
  inventory: Any = get_component(inventory_id)
  return INVENTORY_WRAPPER_CLASS_BY_TYPE_ID[inventory.type_id](inventory)

def home() -> InventoryWrapper:
  return get(HOME_INVENTORY_ID)

def ids_local_to(outpost: OutpostRef) -> tuple[str, ...]:
  local_inventories = [HOME_INVENTORY_ID] if outpost.is_home else []
  local_inventories.extend(
    building.id for building in outpost.buildings() if building.type_id in INVENTORY_WRAPPER_CLASS_BY_TYPE_ID)
  return tuple(local_inventories)

def local_to(outpost: OutpostRef) -> tuple[InventoryWrapper, ...]:
  return tuple(get(inventory_id) for inventory_id in ids_local_to(outpost))
