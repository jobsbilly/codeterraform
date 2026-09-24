from __builtins__ import *

import dataclasses

from workorders import BioWorkOrder
import wrapper

print(f"Starting up: {self.id!r}")

# TODO: Replace hardcoded channel names with pseudo-enum.
REQUESTED_FRAGMENTS_CHANNEL = "requested_fragments"

@dataclasses.dataclass()
class OrderFragment:
  id: str
  requires: int
  in_transit: int = 0
  delivered: int = 0

  @property
  def needed(self) -> int:
    return max(self.requires - self.in_transit - self.delivered, 0)

class BioOrderStatus:
  """Pseudo-Enum of BioOrder.status() return values."""
  ACTIVE = "active"
  AVAILABLE = "available"
  COMPLETE = "complete"

class BioOrderWrapper(wrapper.WrapperBase):
  def __init__(self, value: BioOrder):
    super().__init__(value)
    self._value = value
    self._fragments: tuple[OrderFragment] | None = None

  @property
  def fragments(self) -> tuple[OrderFragment]:
    if self._fragments is not None:
      return self._fragments
    fragments_by_id = {_id: OrderFragment(_id, required) for _id, required in self.requires.items()}
    for _id, in_transit in self.in_transit.items():
      if _id not in fragments_by_id:
        raise RuntimeError(f"Order {self.id!r} has fragment {_id!r} in-transit but none required.")
      fragments_by_id[_id].in_transit = in_transit
    for _id, delivered in self.delivered.items():
      if _id not in fragments_by_id:
        raise RuntimeError(f"Order {self.id!r} has fragment {_id!r} delivered but none required.")
      fragments_by_id[_id].delivered = delivered
    return tuple(fragments_by_id.values())

  def is_available(self) -> bool:
    return self.status == BioOrderStatus.AVAILABLE

  def fragments_needed_by_id(self) -> dict[str, int]:
    return {fragment.id: fragment.needed for fragment in self.fragments if fragment.needed}

  def total_fragments_needed(self) -> int:
    return sum(fragment.needed for fragment in self.fragments)

def known_fragment_ids_around_outpost(outpost: OutpostRef) -> list[str]:
  """Returns fragment IDs that are discovered and accessible by bio collectors from the same outpost."""
  collector_ids = [collector.id for collector in outpost.buildings("bio_collector")]
  if collector_ids:
    collector = get_component(collector_ids[0])
    return [fragment.fragment_id for fragment in collector.scan() if fragment.fragment_id is not None]
  warn(f"No bio collectors found in outpost {outpost.id!r}.")
  return []

class BioExchangeWrapper(wrapper.WrapperBase):
  def __init__(self, value: BioExchange, comms: Comms):
    if comms is None:
      raise TypeError("`comms` cannot be None")
    super().__init__(value)
    self._value = value
    self._comms = comms

  def orders(self) -> tuple[BioOrderWrapper]:
    return tuple(BioOrderWrapper(order) for order in self._value.orders())

  def available_orders(self) -> tuple[BioOrderWrapper]:
    return tuple(order for order in self.orders() if order.is_available())

  def active_order(self) -> BioOrderWrapper | None:
    if (order := self._value.active_order()) is None:
      return None
    return BioOrderWrapper(order)

  # TODO: override BioExchange.clear_order(); have it cancel requested fragments (but only the ones requested by this bio exchange).

  def best_viable_order(self) -> BioOrderWrapper | None:
    viable_orders = [order for order in self.available_orders() if self.outpost.biome == order.biome]
    # Not required, but avoids calls to other components when no viable orders exist.
    if not viable_orders:
      return None
    # Ignore orders that need any components that can't be found locally.
    # TODO: add support for order coordination once I get a second Bio Exchange.
    available_fragment_ids = set(known_fragment_ids_around_outpost(self.outpost))
    viable_local_orders = []
    for order in viable_orders:
      needed_fragment_ids = set(fragment.id for fragment in order.fragments if fragment.needed > 0)
      if not needed_fragment_ids - available_fragment_ids:
        viable_local_orders.append(order)
    # Return the order with the fewest total needed fragments.
    if viable_local_orders:
      return viable_local_orders[0]
    return None

  def request_needed_fragments(self) -> None:
    if (order := self.active_order()) is None:
      raise RuntimeError(f"{self.id!r}: request_needed_fragments() called with no active order")
    if not (fragments_needed_by_id := order.fragments_needed_by_id()):
      warn(f"{self.id!r}: request_needed_fragments() called with no fragments needed")
      return
    for fragment_id, needed_count in fragments_needed_by_id.items():
      work_order = BioWorkOrder(order=order.id, fragment=fragment_id, requester=self.id)
      for _ in range(needed_count):
        if (result := self._comms.send(REQUESTED_FRAGMENTS_CHANNEL, work_order.to_json())).status != "ok":
          raise RuntimeError(result.message)
        # TODO: store result.message_id in Data Archive to allow restart-safe work cancellation.

  def set_order(self, order_id: str) -> None:
    result = self._value.set_order(order_id)
    if result.status == "unknown_order":
      raise ValueError(result.message)
    if result.status == "completed":
      # Unlikely timing, but should be fine.
      print(f"{self.id!r}: tried to activate {order_id!r}, but it was already completed.")
      return
    self.request_needed_fragments()

bio_exchange = BioExchangeWrapper(self, get_component("comms"))

wall_seconds_per_game_hour = get_component("clock").real_seconds_per_hour()
SLEEP_GAME_HOURS_NO_ORDERS = 3

while True:
  if bio_exchange.active_order() is None:
    candidate_order = bio_exchange.best_viable_order()
    if candidate_order is None:
      warn(f"{bio_exchange.id} has no viable orders available to make active; "
           f"sleeping for {SLEEP_GAME_HOURS_NO_ORDERS} game hour(s).")
      sleep(SLEEP_GAME_HOURS_NO_ORDERS * wall_seconds_per_game_hour)
    bio_exchange.set_order(candidate_order.id)

  break  # TODO: delete this line when script is complete.

# print(known_fragment_ids_around_outpost())

# def print_order(odr: BioOrderWrapper):
#   print()
#   print(odr)
#   print(f"Fragments (total needed: {odr.total_fragments_needed()}):")
#   for f in odr.fragments:
#     print(f"  {f}")
#
# all_orders = bio_exchange.orders()
# for odr in all_orders[:4]:
#   print_order(odr)

# print(bio_exchange.best_viable_order())
# print(bio_exchange.clear_order())
