from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import dataclasses
from typing import Any, Callable, Self

import error
from error import raise_if_error
import notebook as notebook_

BIO_ORDERS_KEY = "bio_orders"

_TOTAL_ORDER_COUNT = 80

@dataclasses.dataclass
class Fragment:
  id: str
  needed: int
  coords: list[int | float] | None
  required_genes: list[str] | None


@dataclasses.dataclass
class UnfinishedBioOrder:
  id: str
  biome: str
  fragment_by_id: dict[str, Fragment]
  target_glow: list[int] | None

  @classmethod
  def from_bio_order(cls, order: BioOrder, coords_by_fragment_id: dict[str, list[int | float]]) -> Self:
    fragment_by_id = {}
    required_genes_by_fragment_id = order.required_genes or {}
    for _id, required in order.requires.items():
      if (needed := required - order.in_transit[_id] - order.delivered[_id]) > 0:
        fragment_by_id[_id] = Fragment(id=_id, needed=needed, coords=coords_by_fragment_id.get(_id, None),
                                       required_genes=required_genes_by_fragment_id.get(_id, None))
    return cls(id=order.id, biome=order.biome, fragment_by_id=fragment_by_id, target_glow=order.target_glow)

  @classmethod
  def from_json(cls, order: dict[str, JsonValue], coords_by_fragment_id: dict[str, list[int | float]]) -> Self:
    fragment_by_id = {}
    for _id, fragment in order["fragment_by_id"].items():
      coords = fragment.get("coords", None) or coords_by_fragment_id.get(_id, None)
      fragment_by_id[_id] = Fragment(id=_id, needed=fragment["needed"], coords=coords,
                                     required_genes=fragment["required_genes"])
    return cls(id=order["id"], biome=order["biome"], fragment_by_id=fragment_by_id, target_glow=order["target_glow"])

  def to_json(self) -> dict[str, JsonValue]:
    return dataclasses.asdict(self)

  def undiscovered_fragment_id_count(self) -> int:
    return sum(1 for fragment in self.fragment_by_id.values() if not fragment.coords)

  def total_needed_discovered_fragments(self) -> int:
    return sum(fragment.needed for fragment in self.fragment_by_id.values() if fragment.coords)

  def next_needed_fragment(self) -> tuple[str | None, list[int | float] | None]:
    return next((f.id, f.coords for f in self.fragment_by_id.values() if f.coords and f.needed), (None, None))

  def _save_fragment_by_id(self, owner_id: str, notebook: notebook_.NotebookWrapper) -> None:
    fragment_by_id_json = self.to_json()["fragment_by_id"]
    def tx_fn(value: Any) -> JsonValue:
      value["claimed_by_owner_id"][owner_id]["fragment_by_id"] = fragment_by_id_json
      return value
    raise_if_error(notebook.transaction(BIO_ORDERS_KEY, None, tx_fn))

  def one_less_needed(self, fragment_id: str, owner_id: str, notebook: notebook_.NotebookWrapper) -> None:
    fragment = self.fragment_by_id[fragment_id]
    fragment.needed -= 1
    if fragment.needed == 0:
      del self.fragment_by_id[fragment.id]
    self._save_fragment_by_id(owner_id, notebook)

  def unclaim(self, owner_id: str, notebook: notebook_.NotebookWrapper) -> None:
    def tx_fn(value: Any) -> JsonValue:
      del value["claimed_by_owner_id"][owner_id]
      if sum(fragment.needed for fragment in self.fragment_by_id.values()):
        value["unclaimed_orders"].append(self.to_json())
      else:
        value["completed_or_fully_assigned_order_ids"].append(self.id)
      return value
    raise_if_error(notebook.transaction(BIO_ORDERS_KEY, None, tx_fn))


def get_claimed_order(
    owner_id: str,
    coords_by_fragment_id: dict[str, list[int | float]],
    notebook: notebook_.NotebookWrapper
) -> UnfinishedBioOrder | None:
  order_json = notebook.get(BIO_ORDERS_KEY)["claimed_by_owner_id"].get(owner_id, None)
  return UnfinishedBioOrder.from_json(order_json, coords_by_fragment_id) if order_json else None

# Note: an instance of this type is never populated until the paired function is called.
_ClaimOrderTxReturnValues = TypedDict("_ClaimOrderTxReturnValues", {"order": UnfinishedBioOrder | None})

def _tx_claim_order(
    owner_id: str,
    biome: str,
    coords_by_fragment_id: dict[str, list[int | float]]
) -> tuple[Callable[[JsonValue], JsonValue], _ClaimOrderTxReturnValues]:
  tx_return_values: _ClaimOrderTxReturnValues = {}
  def fn(value: Any) -> JsonValue:
    if owner_id in value["claimed_by_owner_id"]:
      raise error.CodeTerraformError(f"{owner_id!r} already has a claimed order.")
    unclaimed_orders: list[UnfinishedBioOrder] = []
    for order_json in value["unclaimed_orders"]:
      if order_json["biome"] == biome:
        order = UnfinishedBioOrder.from_json(order_json, coords_by_fragment_id)
        if order.total_needed_discovered_fragments() > 0:
          if order.target_glow:
            raise error.CodeTerraformError("Time to add support for target_glow")
          if any(f.required_genes is not None for f in order.fragment_by_id.values()):
            raise error.CodeTerraformError("Time to add support for required_genes")
          unclaimed_orders.append(order)
    if not unclaimed_orders:
      tx_return_values.order = None
      return value

    unclaimed_orders.sort(key=lambda o: (o.undiscovered_fragment_id_count(), o.total_needed_discovered_fragments()))
    claimed_order = unclaimed_orders[0]
    value["unclaimed_orders"] = [o for o in value["unclaimed_orders"] if o["id"] != claimed_order.id]
    value["claimed_by_owner_id"][owner_id] = claimed_order.to_json()

    tx_return_values.order = claimed_order
    return value
  return fn, tx_return_values

def claim_order(
    owner_id: str,
    biome: str,
    coords_by_fragment_id: dict[str, list[int | float]],
    notebook: notebook_.NotebookWrapper
) -> UnfinishedBioOrder | None:
  tx_return_values: _ClaimOrderTxReturnValues
  tx_fn, tx_return_values = _tx_claim_order(owner_id, biome, coords_by_fragment_id)
  raise_if_error(notebook.transaction(BIO_ORDERS_KEY, None, tx_fn))
  return tx_return_values.order

def _tx_populate_table_if_not_exists(bio_exchange: BioExchange, journal: Journal) -> Callable[[JsonValue], JsonValue]:
  def fn(value: JsonValue) -> JsonValue:
    if value is None:
      return value
    print(f"{BIO_ORDERS_KEY!r} table not found in Data Archive; populating now...")
    table = {
      "unclaimed_orders": [],
      "claimed_by_owner_id": {},
      "completed_or_fully_assigned_order_ids": []
    }
    coords_by_fragment_id = {f.fragment_id: f.coords for f in journal.cataloged_fragments("nocturna")}
    for order in bio_exchange.orders():
      if order.status == "complete":
        table["completed_or_fully_assigned_order_ids"].append(order.id)
        continue
      unfinished_order = UnfinishedBioOrder.from_bio_order(order, coords_by_fragment_id)
      table["unclaimed_orders"].append(unfinished_order.to_json())
    return table
  return fn

def populate_table_if_not_exists(
    bio_exchange: BioExchange,
    journal: Journal,
    notebook: notebook_.NotebookWrapper
) -> None:
  # TODO: add support for populating new-to-the-game BioOrders.
  if len(bio_exchange.orders()) != _TOTAL_ORDER_COUNT:
    raise error.CodeTerraformError("Time to add support for populating new-to-the-game BioOrders")
  tx_fn = _tx_populate_table_if_not_exists(bio_exchange, journal)
  raise_if_error(notebook.transaction(BIO_ORDERS_KEY, None, tx_fn))

def all_work_assigned(biome: str, notebook: notebook_.NotebookWrapper) -> bool:
  table = notebook._value.get(BIO_ORDERS_KEY)
  return not any(o["biome"] == biome for o in chain(table["unclaimed_orders"], table["claimed_by_owner_id"].values()))
