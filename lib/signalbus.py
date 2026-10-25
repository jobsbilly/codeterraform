from typing import Self

from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import enum
import re

import error
import wrapper


CHANNEL_PART_DELIMITER = ":"
MAX_CHANNEL_ID_LEN = 64


class ChannelIDError(error.CodeTerraformError):
  pass


def make_channel_id(*parts: str) -> str:
  channel_id = CHANNEL_PART_DELIMITER.join(parts)
  if not channel_id:
    raise ChannelIDError("Must be a non-empty string")
  if len(channel_id) > MAX_CHANNEL_ID_LEN:
    raise ChannelIDError(f"{channel_id!r} exceeds max length of {MAX_CHANNEL_ID_LEN}")
  if re.search(r"[^\w.:-]", channel_id) is not None:
    raise ChannelIDError(f"{channel_id!r} contains invalid characters")
  return channel_id


# Helps prevent accidental channel ID collisions.
class ChannelIDRoot(enum.StrEnum):
  """Directory of all channel ID roots (which may be the entire ID, if the ChannelScope is UNIVERSAL)."""
  # BioOrders
  REQUESTED_FRAGMENTS = "requested_fragments"
  COLLECTED_FRAGMENTS = "collected_fragments"
  EXTRACTED_SAMPLES = "extracted_samples"
  PREPARED_SAMPLES = "prepared_samples"
  # Couriers
  COURIER_REQUESTS = "courier_requests"
  COURIER_DELIVERIES = "courier_deliveries"

  # Makes sure all member values adhere to format rules.
  def __new__(cls, value: str):
    make_channel_id(value)  # Raises if value breaks the rules.
    member = str.__new__(cls, value)
    member._value_ = value
    return member


class ChannelScope(enum.Enum):
  UNIVERSAL = enum.auto()
  BIOME = enum.auto()
  OUTPOST = enum.auto()
  TARGET = enum.auto()


class ChannelBase(enum.Enum):
  def __init__(self, id_root: str, scope: ChannelScope):
      self._id_root = id_root
      self._scope = scope

  def id(self, *, biome: str | None = None, outpost: str | None = None, target: str | None = None) -> str:
    if self._scope is ChannelScope.UNIVERSAL:
      return make_channel_id(self._id_root)
    if self._scope is ChannelScope.BIOME:
      if not biome:
        raise error.CodeTerraformError(f"`biome` must be non-empty for {self.name} channel")
      return make_channel_id(self._id_root, biome)
    if self._scope is ChannelScope.OUTPOST:
      if not outpost:
        raise error.CodeTerraformError(f"`outpost` must be non-empty for {self.name} channel")
      return make_channel_id(self._id_root, outpost)
    if self._scope is ChannelScope.TARGET:
      if not target:
        raise error.CodeTerraformError(f"`target` must be non-empty for {self.name} channel")
      return make_channel_id(self._id_root, target)
    raise error.CodeTerraformError(f"Unrecognized scope: {self._scope!r}")


class CommsError(error.CodeTerraformError):
  pass


class CommsWrapper(wrapper.WrapperBase):
  def __init__(self, value: Comms):
    super().__init__(value)
    self._value: Comms
    self._channel_id_by_channel: dict[ChannelBase, str] = {}

  def register(self, channel: ChannelBase, **kwargs) -> Self:
    self._channel_id_by_channel[channel] = channel.id(**kwargs)
    return self

  def forget(self, channel: ChannelBase) -> None:
    if self._channel_id_by_channel.pop(channel, None) is None:
      warn(f"Tried to forget unregistered channel: {channel!r}")

  def channel_id(self, channel: ChannelBase) -> str:
    if (channel_id :=  self._channel_id_by_channel.get(channel, None)) is None:
      raise CommsError(f"Channel {channel!r} must be registered on this {type(self)} before use")
    return channel_id

  # Explicit return type hints are intentionally omitted below - inferred types from the underlying Comms.* methods are
  # more precise (e.g., I would specify `ActionResult`, but the inferred type is `ActionResult[Literal["ok", ...]]`).
  def send(self, channel: ChannelBase, value: JsonValue):
    return self._value.send(self.channel_id(channel), value)

  def receive(self, channel: ChannelBase, message_id: int | None = None):
    return self._value.receive(self.channel_id(channel), message_id)

  def wait(self, channel: ChannelBase):
    channel_id = self.channel_id(channel)
    debug(f"BLOCK: wait({channel_id!r})")
    result = self._value.wait(channel_id)
    debug(f"RESUME: wait({channel_id!r})")
    return result

  def wait_any(self, channels: list[ChannelBase]):
    channel_ids = [self.channel_id(channel) for channel in channels]
    debug(f"BLOCK: wait_any({channel_ids!r})")
    result = self._value.wait_any(channel_ids)
    debug(f"RESUME: wait_any({channel_ids!r})")
    return result

  def wait_broadcast(self, channel: ChannelBase):
    channel_id = self.channel_id(channel)
    debug(f"BLOCK: wait_broadcast({channel_id!r})")
    result = self._value.wait_broadcast(channel_id)
    debug(f"RESUME: wait_broadcast({channel_id!r})")
    return result

  def pending(self, channel: ChannelBase):
    return self._value.pending(self.channel_id(channel))

  def broadcast(self, channel: ChannelBase, value: JsonValue):
    return self._value.broadcast(self.channel_id(channel), value)
