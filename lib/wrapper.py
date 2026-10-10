from __builtins__ import Component, object_type

from typing import Any, Iterable


class WrapperBase:
  def __init__(self, value: Any, required: Iterable[Any] = ()):
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
  def __init__(self, value: Component, required: Iterable[Any] = ()):
    super().__init__(value, required)
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
