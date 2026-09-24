from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import dataclasses
from typing import Self

@dataclasses.dataclass
class BioWorkOrder:
  order: str | None = None
  fragment: str | None = None
  requester: str | None = None
  coords: list[float | int] | None = None
  collector: str | None = None
  lab: str | None = None

  def to_json(self) -> dict[str, JsonValue]:
    return {k: v for k, v in dataclasses.asdict(self).items() if v is not None}

  @classmethod
  def from_json(cls, value: dict[str, JsonValue]) -> Self:
    return cls(**value)
