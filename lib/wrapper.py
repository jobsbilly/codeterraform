class WrapperBase:
  def __init__(self, value):
    if value is None:
      raise TypeError(f"{type(self)} cannot wrap None")
    self._value = value

  def __getattr__(self, name):
    try:
      return getattr(self._value, name)
    except AttributeError:
      raise AttributeError(f"{type(self)} has no attribute {name!r}")

  def __repr__(self) -> str:
    return repr(self._value)