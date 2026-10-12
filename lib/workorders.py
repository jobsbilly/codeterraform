from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import dataclasses
from typing import Any, Callable, Self

import notebook as notebooklib
from signalbus import ChannelBase, ChannelIDRoot, ChannelScope

WORK_ORDERS_KEY = "work_orders_by_worker_id"


class _WorkOrderBase:
  def to_json(self) -> dict[str, JsonValue]:
    return {k: v for k, v in dataclasses.asdict(self).items() if v is not None}

  @classmethod
  def from_json(cls, value: dict[str, JsonValue]) -> Self:
    return cls(**value)

  @classmethod
  def from_comms_message(cls, packet: Any) -> Self:
    return cls.from_json(packet.value)

  def tx_setter(self, worker_id: str) -> Callable[[dict[str, JsonValue]], dict[str, JsonValue]]:
    work_order = self.to_json()
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

  def claim(self, worker_id: str, notebook: notebooklib.NotebookWrapper) -> ActionResult:
    return notebook.transaction(WORK_ORDERS_KEY, {}, self.tx_setter(worker_id))

  @classmethod
  def release(cls, worker_id: str, notebook: notebooklib.NotebookWrapper) -> ActionResult:
    return notebook.transaction(WORK_ORDERS_KEY, {}, cls.tx_deleter(worker_id))

  @classmethod
  def get_claimed(cls, worker_id: str, notebook: notebooklib.NotebookWrapper) -> Self | None:
    work_order_by_worker_id = notebook.get(WORK_ORDERS_KEY, {})
    if (work_order_json := work_order_by_worker_id.get(worker_id, None)) is None:
      return None
    return cls.from_json(work_order_json)


@dataclasses.dataclass
class BioWorkOrder(_WorkOrderBase):
  order: str | None = None
  fragment: str | None = None
  requester: str | None = None
  coords: list[float | int] | None = None
  collector: str | None = None
  lab: str | None = None

  class Channel(ChannelBase):
    REQUESTED_FRAGMENTS = (ChannelIDRoot.REQUESTED_FRAGMENTS, ChannelScope.BIOME)
    COLLECTED_FRAGMENTS = (ChannelIDRoot.COLLECTED_FRAGMENTS, ChannelScope.OUTPOST)
    PREPARED_SAMPLES = (ChannelIDRoot.PREPARED_SAMPLES, ChannelScope.OUTPOST)
