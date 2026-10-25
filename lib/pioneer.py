from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import collections
import dataclasses
import enum
import itertools
import math
from typing import Iterable

from error import CodeTerraformError, raise_if_none
import notebook as notebooklib
import signalbus
from status import assign_or_raise, raise_if_error
from workorders import CourierWorkOrder
import wrapper

SPORT_NAV_MODULE_ID = "nav_module_sport"
RANGE_AFFECTING_MODULES = (
  "nav_module",
  SPORT_NAV_MODULE_ID,
  "sonar_module",
  "sonar_module_wide",
  "sonar_module_deep",
  "drill_module",
  "drill_module_industrial",
  "drill_module_heavy",
  "constructor_module",
)
PROXIMITY_RADIUS_METERS = 2
BASE_TOP_SPEED_METERS_PER_HOUR = 100

def in_proximity(coords: list[float], other_coords: list[float]) -> bool:
  return math.dist(coords, other_coords) < PROXIMITY_RADIUS_METERS

def wh_per_m(throttle: float, cargo_count: int, modules: Iterable[MountSlot]) -> float:
  heavy_module_count_by_id = collections.Counter(
    m.module_id for m in modules if m.module_id in RANGE_AFFECTING_MODULES)
  heavy_module_count = heavy_module_count_by_id.total()
  sport_nav_count = heavy_module_count_by_id[SPORT_NAV_MODULE_ID]

  wh_per_m_before_sport_navs = (0.03 + 0.08 * heavy_module_count + 0.0004 * cargo_count) * throttle ** 0.5
  speed_multiplier = sport_nav_count + 1
  wh_multiplier = 1 + 1.25 * sport_nav_count + 0.35 * sport_nav_count ** 2

  return wh_per_m_before_sport_navs / speed_multiplier * wh_multiplier

def move_cost_wh(
    coords: list[float],
    target: list[float],
    throttle: float = 1,
    cargo_count: int = 0,
    *,
    modules: Iterable[MountSlot],
) -> float:
  distance_meters = math.dist(coords, target)
  if distance_meters < PROXIMITY_RADIUS_METERS:
    return 0
  return distance_meters * wh_per_m(throttle, cargo_count, modules)

def all_charging_station_coords(outpost_network: OutpostNetwork) -> tuple[list[float]]:
  return tuple(outpost.coords()
               for outpost in outpost_network.outposts()
               if any(charger.powered for charger in outpost.buildings("charging_station")))

def closest_charging_station_coords(coords: list[float], outpost_network: OutpostNetwork) -> list[float]:
  if not (all_charger_coords := all_charging_station_coords(outpost_network)):
    raise CodeTerraformError("No (powered) charging stations found")
  return sorted(all_charger_coords, key=lambda charger_coords: math.dist(coords, charger_coords))[0]


class PioneerWrapper(wrapper.MachineWrapper):
  def __init__(self, value: Pioneer, clock: Clock, outpost_network: OutpostNetwork, **kwargs):
    required = itertools.chain((clock, outpost_network), kwargs.pop("required", ()))
    super().__init__(value, required=required)
    self._value: Pioneer
    self._clock = clock
    self._outpost_network = outpost_network

  # TODO: move cargo-related functions into a new CargoWrapper class.
  def space_for(self, item_id: str) -> int:
    available = 0
    for rack in self.cargo.racks():
      for bin_ in rack.bins:
        if bin_.item_id and bin_.item_id != item_id:
          continue  # Bins can only contain one item_id.
        available += bin_.capacity - bin_.count
    return available

  def has_space(self, item_id: str, quantity: int) -> bool:
    return self.space_for(item_id) >= quantity

  def load(self, item_id: str, quantity: int = 1, source: str = "inventory") -> None:
    if not self.has_space(item_id, quantity):
      raise CodeTerraformError(f"Aborted; not enough space to load {quantity} {item_id}")
    raise_if_error(self.input.connect(source))
    raise_if_error(self.input.take(item_id, quantity))  # Blocks for 2.5 ticks per item (total rounded up).
    raise_if_error(self.input.disconnect())

  def unload(self, item_id: str, quantity: int = 1, destination: str = "inventory") -> None:
    quantity_in_cargo = sum(stack.count for stack in self.cargo.stacks() if stack.id == item_id)
    if quantity > quantity_in_cargo:
      raise CodeTerraformError(f"Aborted; tried to unload {quantity} {item_id!r}, but cargo only has "
                               f"{quantity_in_cargo}")
    raise_if_error(self.output.connect(destination))
    unsent_count = quantity
    for stack in self.cargo.stacks():
      if stack.id != item_id:
        continue
      send_quantity = min(stack.count, unsent_count)
      raise_if_error(self.output.send(stack.id, send_quantity))  # Blocks for 2.5 ticks per item.
      unsent_count -= send_quantity
      if unsent_count == 0:
        break
    raise_if_error(self.output.disconnect())

  def unload_all(self, item_id: str | None = None, destination: str = "inventory") -> int:
    raise_if_error(self.output.connect(destination))
    total_count = 0
    for stack in self.cargo.stacks():
      if item_id is None or stack.id == item_id:
        total_count += stack.count
        raise_if_error(self.output.send(stack.id, stack.count))  # Blocks for 2.5 ticks per item.
    raise_if_error(self.output.disconnect())
    return total_count

  def coords(self) -> list[float]:
    return list(self.nav.get_position())

  def is_at(self, target: list[float]) -> bool:
    return in_proximity(self.coords(), target)

  def get_move_cost_wh(self, target: list[float], throttle: float = 1) -> float:
    return move_cost_wh(self.coords(), target, throttle, self.cargo.count(), modules=self.modules())

  def goto(self, target: list[float], throttle: float | None = None) -> None:
    if self.is_at(target):
      debug(f"Already at {target=}.")
      return

    if not throttle:
      # Find the fastest throttle with the necessary range.
      throttle = 1
      while self.get_move_cost_wh(target, throttle) > self.battery.wh():
        throttle -= 0.05
        if throttle < 0.049:
          raise CodeTerraformError(f"{target} is unreachable at any throttle (with current loadout)")
    elif self.get_move_cost_wh(target, throttle) > self.battery.wh():
      raise CodeTerraformError(f"{target} is unreachable at {throttle=} (with current loadout)")

    raise_if_error(self.nav.set_target(*target))
    raise_if_error(self.nav.set_throttle(throttle))

    # Sleep for most of the trip (but wake up with plenty of time to brake).
    game_hours_until_arrival = (
        self.nav.get_distance_to(*target) / (BASE_TOP_SPEED_METERS_PER_HOUR * self.nav.speed_multiplier()))
    real_seconds_until_arrival = game_hours_until_arrival * self._clock.real_seconds_per_hour()
    debug(f"Estimated travel time from {list(self.nav.get_position())} to {target} is {real_seconds_until_arrival} sec")
    if real_seconds_until_arrival > 3:
      sleep(real_seconds_until_arrival - 3)

    while not in_proximity(self.coords(), target):
      pass
    raise_if_error(self.nav.brake())
    debug(f"{target=} reached.")

  def survey_sites_in_range(self) -> None:
    if not any(m.module_id.startswith("sonar_") for m in self._value.modules() if m.module_id is not None):
      warn(f"Aborted: {self.id!r} has no sonar module mounted.")
      return
    for site in assign_or_raise(self.sonar.scan(), "sites"):
      if not site.surveyed:
        print(f"Surveyed new site: {assign_or_raise(self.sonar.survey(site))}")

  def recharge(self, *, disallow_movement: bool = False) -> None:
    if not self.current_station():
      if disallow_movement:
        raise CodeTerraformError(f"No charging station at current location ({self.coords()})")
      if (coords := closest_charging_station_coords(self.coords(), self._outpost_network)) is None:
        raise CodeTerraformError("No (powered) charging stations found")
      debug("Going to nearest charging station...")
      self.goto(coords)

    station: ChargingStation = get_component(self.current_station())  # type: ignore
    if station is None:
      raise CodeTerraformError("No charging station found! A `sleep(0.1)` may be necessary after `self.goto()`")
    bay_count = station.get_bay_count()
    # If a bay isn't available right away, check every second until one is.
    while self.id in (queue := station.get_queue()) and self.id not in queue[:bay_count]:
      sleep(1)

    waited_for_full_charge_count = 0
    while self.battery.level() < 0.998:
      if waited_for_full_charge_count > 4:
        raise CodeTerraformError(f"Battery not fully charged after {waited_for_full_charge_count} attempts")
      if waited_for_full_charge_count > 1:
        warn(f"Repeated misses of the estimated time to full charge: {waited_for_full_charge_count} times.")
      if waited_for_full_charge_count == 1:
        debug("Missed the estimated time to full charge once. Another vehicle may have docked during charging.")
      watts_needed = self.battery.capacity() - self.battery.wh()

      stopwatch_start_seconds = self._clock.elapsed_seconds()
      while (watts_per_game_hour := station.get_charge_rate(self.id)) == 0 and self.battery.level() < 0.998:
        sleep(0.2)
        if (elapsed_seconds := self._clock.elapsed_seconds() - stopwatch_start_seconds) > 120:
          raise CodeTerraformError(f"Charge rate was zero for at least {elapsed_seconds} seconds; battery = "
                                   f"{self.battery.level()}; {station.id} queue: {station.get_queue()}")

      # Add an extra tick of buffer time.
      charge_duration_seconds = watts_needed / watts_per_game_hour * self._clock.real_seconds_per_hour() + 0.1
      debug(f"Sleeping {charge_duration_seconds} until estimated full charge...")
      sleep(charge_duration_seconds)
      waited_for_full_charge_count += 1


class WaypointAction(enum.StrEnum):
  START = enum.auto()
  PICKUP = enum.auto()
  DELIVER = enum.auto()
  RECHARGE = enum.auto()


@dataclasses.dataclass
class RouteWaypoint:
  coords: list[float]
  action: WaypointAction
  cargo_count_by_item_id: dict[str, int] | None = None
  throttle: float = 1

  def __post_init__(self):
    cargo_count = self.cargo_count()
    if self.action is WaypointAction.DELIVER and cargo_count == 0:
      raise CodeTerraformError(f"DELIVER waypoints must have 1+ cargo count: {self}")
    if self.action is WaypointAction.PICKUP and cargo_count != 0:
      raise CodeTerraformError(f"PICKUP waypoints cannot have cargo: {self}")

  def cargo_count(self) -> int:
    if self.cargo_count_by_item_id is None:
      return 0
    cargo_count = 0
    for item_count in self.cargo_count_by_item_id.values():
      if item_count < 0:
        raise CodeTerraformError(f"Found negative count in {self.cargo_count_by_item_id=}")
      cargo_count += item_count
    return cargo_count


def _append_and_auto_chunk(
    chunks: list[list[RouteWaypoint]],
    waypoint: RouteWaypoint,
    all_charger_coords: Iterable[list[float]]
) -> None:
  """Start a new chunk if the last waypoint has a charger; otherwise, add `waypoint` to the last chunk."""
  last_coords = chunks[-1][-1].coords
  if any(in_proximity(last_coords, charger) for charger in all_charger_coords):
    # Start the new chunk with an explicit RECHARGE action at the last waypoint's coords.
    # Including waypoint's cargo info allows any PICKUP waypoint to pull from its next waypoint for the cargo manifest.
    chunks.append([RouteWaypoint(last_coords, WaypointAction.RECHARGE, waypoint.cargo_count_by_item_id), waypoint])
  else:
    chunks[-1].append(waypoint)


class CourierPioneerWrapper(PioneerWrapper):
  def __init__(
      self,
      value: Pioneer,
      clock: Clock,
      outpost_network: OutpostNetwork,
      comms: signalbus.CommsWrapper,
      notebook: notebooklib.NotebookWrapper,
  ):
    super().__init__(value, clock, outpost_network, required=(comms, notebook))
    self._comms = comms.register(CourierWorkOrder.Channel.REQUESTS)
    self._notebook = notebook

    if not self.cargo.capacity():
      raise CodeTerraformError("Couriers must be able to carry cargo")

  def _block_until_work(self) -> CourierWorkOrder:
    comms_message = assign_or_raise(self._comms.wait(CourierWorkOrder.Channel.REQUESTS))

    work_order = CourierWorkOrder.from_comms_message(comms_message)
    work_order.courier = self.id

    # Persist the work order while working on it; if it fails, put the unmodified work order back before letting the
    # exception propagate.
    try:
      raise_if_error(work_order.claim(self.id, self._notebook))
    except Exception:
      raise_if_error(self._comms.send(CourierWorkOrder.Channel.REQUESTS, comms_message.value))
      raise

    return work_order

  def _next_batch_and_remainder(self, needed_count_by_item_id: dict[str, int]) -> tuple[dict[str, int], dict[str, int]]:
    if self.cargo.count():
      raise CodeTerraformError("Cargo must be empty")
    if sum(needed_count_by_item_id.values()) == 0:
      warn("Called without any needed items.")
      return {}, {}
    cargo_bin_capacities = tuple(
      sorted((bin_.capacity for rack in self.cargo.racks() for bin_ in rack.bins), reverse=True))
    used_bin_count = 0
    next_batch = collections.Counter()
    for item_id, needed_count in needed_count_by_item_id.items():
      available_bin_count = len(cargo_bin_capacities) - used_bin_count
      if int(available_bin_count) == 0:
        break  # No available bins; remaining items will be handled by subsequent trips.
      if needed_count == 0:
        warn(f"Called with {item_id} needing 0.")
        break
      for bin_index in range(available_bin_count):
        used_bin_count += 1
        next_batch[item_id] += min(needed_count - next_batch[item_id], cargo_bin_capacities[bin_index])
        if needed_count == next_batch[item_id]:
          break
    return dict(next_batch), dict(collections.Counter(needed_count_by_item_id) - next_batch)

  def _cargo_batches(self, needed_count_by_item_id: dict[str, int]) -> list[dict[str, int]]:
    if self.cargo.capacity() == 0:
      raise CodeTerraformError("No cargo capacity")
    if not any(needed_count_by_item_id.values()):
      raise CodeTerraformError(f"Must have at least one needed item in {needed_count_by_item_id=}")
    if any(needed < 0 for needed in needed_count_by_item_id.values()):
      raise CodeTerraformError(f"Found negative needed count in {needed_count_by_item_id=}")

    batches = []
    while any(needed > 0 for needed in needed_count_by_item_id.values()):
      batch, needed_count_by_item_id = self._next_batch_and_remainder(needed_count_by_item_id)
      batches.append(batch)
    return batches

  def _plan_route(self, work_order: CourierWorkOrder) -> collections.deque[RouteWaypoint]:
    # Chunk boundaries are recharge opportunities.
    route_chunks: list[list[RouteWaypoint]] = [[RouteWaypoint(self.coords(), WaypointAction.START)]]
    all_charger_coords = all_charging_station_coords(self._outpost_network)
    for cargo_count_by_item_id in self._cargo_batches(work_order.needed_count_by_item_id):
      _append_and_auto_chunk(route_chunks, RouteWaypoint(work_order.pickup_coords, WaypointAction.PICKUP),
                             all_charger_coords)
      _append_and_auto_chunk(route_chunks,
                             RouteWaypoint(work_order.delivery_coords, WaypointAction.DELIVER, cargo_count_by_item_id),
                             all_charger_coords)

    # If the last waypoint doesn't have a charging station, add a final recharge waypoint to make sure the pioneer
    # doesn't end up stranded.
    closest_charger_coords = closest_charging_station_coords(route_chunks[-1][-1].coords, self._outpost_network)
    if not in_proximity(route_chunks[-1][-1].coords, closest_charger_coords):
      route_chunks[-1].append(RouteWaypoint(closest_charger_coords, WaypointAction.RECHARGE))

    # Find the fastest viable throttles to use when traveling to each waypoint, or raise an error if no solution exists.
    def get_wh_cost(chunk_: list[RouteWaypoint]) -> float:
      return sum(move_cost_wh(prev.coords, curr.coords, curr.throttle, curr.cargo_count(), modules=self.modules())
                 for prev, curr in itertools.pairwise(chunk_))
    for chunk_index, chunk in enumerate(route_chunks):
      while get_wh_cost(chunk) > self.battery.capacity():
        for waypoint in chunk:
          waypoint.throttle -= 0.05
          if waypoint.throttle < 0.049:
            raise CodeTerraformError(
              f"Route is not viable; not enough power for {chunk_index=} of route: {route_chunks}")

    route = collections.deque(itertools.chain.from_iterable(route_chunks))
    # Discard the START waypoint, as it was only meaningful for route planning.
    route.popleft()
    return route

  def _pickup(self, work_order: CourierWorkOrder, count_to_load_by_item_id: dict[str, int]) -> None:
    for item_id, count_to_load in count_to_load_by_item_id.items():
      work_order.needed_count_by_item_id[item_id] -= count_to_load
      if work_order.needed_count_by_item_id[item_id] < 0:
        raise CodeTerraformError(f"Waypoint specified {count_to_load} {item_id} for PICKUP, but work order only needs "
                                 f"{count_to_load + work_order.needed_count_by_item_id[item_id]}")
      if work_order.needed_count_by_item_id[item_id] == 0:
        del work_order.needed_count_by_item_id[item_id]
      raise_if_error(work_order.save(self.id, self._notebook))
      # If the script stops after work_order.save() returns but before self.input.take() is called, then this item
      # ID/count will be forgetten (i.e., it will never be delivered). This *should* be very unlikely, but isn't
      # impossible.
      self.load(item_id, count_to_load, work_order.pickup_inventory_id)

  def _deliver(self, work_order: CourierWorkOrder, count_to_unload_by_item_id: dict[str, int]) -> None:
    if work_order.delivery_inventory_id is None:
      # TODO: Support this case.
      raise NotImplementedError("Passive unloading")

    for item_id, count_to_unload in count_to_unload_by_item_id.items():
      self.unload(item_id, count_to_unload, work_order.delivery_inventory_id)
    if self.cargo.count() > 0:
      warn(f"Unloaded everything in count_to_unload_by_item_id, but cargo is not empty: {self.cargo.stacks()}")

  def _report_complete_and_release(self, work_order: CourierWorkOrder) -> None:
    if work_order.requester:
      self._comms.register(CourierWorkOrder.Channel.DELIVERIES, target=work_order.requester)
      raise_if_error(self._comms.send(CourierWorkOrder.Channel.DELIVERIES, work_order.to_json()))
      self._comms.forget(CourierWorkOrder.Channel.DELIVERIES)

    raise_if_error(work_order.release(self.id, self._notebook))

  def _prepare_for_main_loop(self) -> None:
    if (initial_status := self.status()) != "idle":
      debug(f"{initial_status=}; waiting until idle...")
      prev_status = initial_status
      while (status := self.status()) != "idle":
        if status != prev_status:
          debug(f"New non-idle status: {status}")
        prev_status = status
      debug("Status is now idle; continuing with startup...")

    work_order = CourierWorkOrder.get_claimed(self.id, self._notebook)
    if work_order is None:
      # For Pioneer, input and output buffers are identical to the cargo, so no need for separate checks.
      if self.cargo.count() > 0:
        raise CodeTerraformError("Found non-empty cargo without a work order during startup.")
      return

    if self.cargo.count() > 0:
      if work_order.requested_count_by_item_id == work_order.needed_count_by_item_id:
        raise CodeTerraformError("Found non-empty cargo before claimed work order's first pickup")

      cargo_count_by_item_id = collections.Counter()
      for stack in self.cargo.stacks():
        cargo_count_by_item_id[stack.id] += stack.count
      for item_id, count in cargo_count_by_item_id.items():
        if item_id not in work_order.requested_count_by_item_id:
          raise CodeTerraformError(f"Found {count} {item_id} in cargo, which wasn't requested by the claimed order")
        if count + work_order.needed_count_by_item_id.get(item_id, 0) > work_order.requested_count_by_item_id[item_id]:
          raise CodeTerraformError(f"Found too much {item_id} in cargo for what the claimed order requested")

      # If still at the pickup site, put all cargo back there.
      if self.is_at(work_order.pickup_coords):
        for item_id, count in cargo_count_by_item_id.items():
          work_order.needed_count_by_item_id[item_id] = work_order.needed_count_by_item_id.get(item_id, 0) + count
          raise_if_error(work_order.save(self.id, self._notebook))
          self.unload_all(item_id, work_order.pickup_inventory_id)
        return
      # Otherwise, deliver it.
      self.goto(work_order.delivery_coords)
      self._deliver(work_order, cargo_count_by_item_id)

    if sum(work_order.needed_count_by_item_id.values()) == 0:
      self._report_complete_and_release(work_order)

  def _main_loop_iteration(self) -> bool:
    existing_work_order = CourierWorkOrder.get_claimed(self.id, self._notebook)
    # If not already in the middle of something, recharge before taking on work.
    if existing_work_order is None and self.battery.level() < 1:
      self.recharge()

    work_order = existing_work_order or self._block_until_work()

    route = self._plan_route(work_order)
    while route:
      waypoint = route.popleft()
      self.goto(waypoint.coords, waypoint.throttle)  # Blocks until arrival.
      if waypoint.action is WaypointAction.PICKUP:
        if not (count_to_load_by_item_id := route[0].cargo_count_by_item_id):
          raise CodeTerraformError(f"Waypoint following PICKUP has no cargo: {route[0]}")
        self._pickup(work_order, count_to_load_by_item_id)
      elif waypoint.action is WaypointAction.DELIVER:
        self._deliver(work_order, raise_if_none(waypoint.cargo_count_by_item_id))
        if sum(work_order.needed_count_by_item_id.values()) == 0:
          self._report_complete_and_release(work_order)
      elif waypoint.action is WaypointAction.RECHARGE:
        self.recharge(disallow_movement=True)
      else:
        raise CodeTerraformError(f"Not supported: {waypoint.action!r}")

    return True
