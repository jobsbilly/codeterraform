from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import dataclasses
from typing import Any, Callable, Self

WORK_ORDERS_KEY = "work_orders_by_worker_id"

@dataclasses.dataclass
class BioWorkOrder:
  order: str | None = None
  fragment: str | None = None
  requester: str | None = None
  coords: list[float | int] | None = None
  collector: str | None = None
  lab: str | None = None

  def tx_setter(self, worker_id: str) -> Callable[[dict[str, JsonValue]], dict[str, JsonValue]]:
    work_order = dataclasses.asdict(self)
    def fn(work_orders_by_worker_id: dict[str, JsonValue]) -> dict[str, JsonValue]:
      work_orders_by_worker_id[worker_id] = work_order
      return work_orders_by_worker_id
    return fn

  @staticmethod
  def tx_deleter(worker_id: str) -> Callable[[dict[str, JsonValue]], dict[str, JsonValue]]:
    def fn(work_orders_by_worker_id: dict[str, JsonValue]) -> dict[str, JsonValue]:
      del work_orders_by_worker_id[worker_id]
      return work_orders_by_worker_id
    return fn

  def to_json(self) -> dict[str, JsonValue]:
    return {k: v for k, v in dataclasses.asdict(self).items() if v is not None}

  @classmethod
  def from_json(cls, value: dict[str, JsonValue]) -> Self:
    return cls(**value)

  @classmethod
  def from_comms_message(cls, packet: Any) -> Self:
    return cls.from_json(packet.value)
