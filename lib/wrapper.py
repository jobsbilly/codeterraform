from __builtins__ import Component, object_type, OutputSlot, sleep

from error import CodeTerraformError
import functools
from typing import Any, Callable, Iterable


class WrapperBase:
  def __init__(self, value: Any, *, required: Iterable[Any] = ()):
    if value is None:
      raise TypeError(f"{type(self)} cannot wrap None")
    for i, arg in enumerate(required):
      if arg is None:
        raise TypeError(f"required[{i}] cannot be None")
    self._value = value

  def __getattr__(self, name):
    try:
      return getattr(self._value, name)
    except AttributeError:
      raise AttributeError(f"{type(self)} has no attribute {name!r}")

  def __repr__(self) -> str:
    return repr(self._value)


class MachineWrapper(WrapperBase):
  def __init__(self, value: Component, *, required: Iterable[Any] = ()):
    super().__init__(value, required=required)
    if (obj_type := object_type(value)) != "Component":
      raise TypeError(f"{type(self)} cannot wrap non-Component {obj_type} type")

  def _prepare_for_main_loop(self) -> None:
    raise NotImplementedError()

  def _main_loop_iteration(self) -> bool:
    raise NotImplementedError()

  def _main_loop(self) -> None:
    while self._main_loop_iteration():
      pass

  def run(self) -> None:
    print(f"SETUP: {self.id!r}")
    self._prepare_for_main_loop()
    print(f"START: {self.id!r}")
    self._main_loop()
    print(f"SHUTDOWN: {self.id!r}")

  def run_single_iteration(self) -> None:
    print(f"SETUP (single-loop): {self.id!r}")
    self._prepare_for_main_loop()
    print(f"START (single-loop): {self.id!r}")
    self._main_loop_iteration()
    print(f"SHUTDOWN (single-loop): {self.id!r}")


def wait_until_clear(
    seconds: float = 0.3,
    max_attempts: int | None = None,
    item_id: str | None = None,
    item_id_getter: Callable[[MachineWrapper], str] | None = None,
    output_getter: Callable[[MachineWrapper], OutputSlot] | None = None,
):
  """Only let an item move into an output when it can be safely disambiguated from other items in that output."""
  def decorator(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
      _max_attempts = max_attempts or 0  # Zero mean indefinitely.
      _item_id = item_id or item_id_getter(self)
      output = output_getter(self) if output_getter is not None else self.output
      attempts = 0
      while any(_item_id == stack.id for stack in output.stacks()):
        if (attempts := attempts + 1) == _max_attempts:
          raise CodeTerraformError(f"{_item_id} in output did not clear")
        sleep(seconds)
      return func(self, *args, **kwargs)
    return wrapper
  return decorator
