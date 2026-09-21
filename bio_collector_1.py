from __builtins__ import *

import wrapper

print(f"Starting up: {self.id!r}")

class BioCollectorWrapper(wrapper.WrapperBase):
  def __init__(self, value: BioCollector, clock: Clock):
    if clock is None:
      raise TypeError("`clock` cannot be None")
    super().__init__(value)
    self._value = value
    self._clock = clock
    self._cargo_filled_at: float | None = None
    if self.cargo is not None:
      self._mark_cargo_full()

  def _mark_cargo_full(self) -> None:
    if self.cargo is None:
      raise RuntimeError("Cargo was not full")
    self._cargo_filled_at = float(self._clock.elapsed_game_hours())

  def collect(self, coords: list[int]) -> None:
    if (result := self._value.collect(coords)).status != "ok":
      raise RuntimeError(result.message)
    self._mark_cargo_full()

  def game_hours_with_cargo_full(self) -> float:
    # if not self._cargo_filled_at:
    if self.cargo is None:
      return 0
    return self._clock.elapsed_game_hours() - self._cargo_filled_at

bio_collector = BioCollectorWrapper(self, get_component("clock"))

TOO_MANY_GAME_HOURS_FOR_CARGO_UNLOADING = 2  # TODO: refine this value (currently a wild guess).

while True:
  # Check if self.cargo has stuff in it.
  # TODO: Figure out what to do with unexpectedly-occupied cargo.
  game_hours_with_cargo_full = bio_collector.game_hours_with_cargo_full()
  if game_hours_with_cargo_full > TOO_MANY_GAME_HOURS_FOR_CARGO_UNLOADING:
    notify(f"{bio_collector.id!r} has been stuck with full cargo for {game_hours_with_cargo_full:.2f} game hours",
           level="warn", duration_seconds=0)

  # Once it's known that self isn't mid-task, choose a task to work on.
  # Possible tasks:
  # 1.  Work on an order.
        # Check if there's already an active order that still needs fragments.
        # Note: don't forget to check the bio lab for in-process fragments.
  # 2.  Fetch unidentified fragments for analysis.
  # 3.  Complete catalogue entries (or not - this is probably naturally covered by #2
  # 4.  Wait for a new order.

  break  # TODO: delete this line when script is complete.

# print(self.outpost)

# print(f"{self.type_id=}")
#
# for fragment in self.scan():
#   print(fragment)

for fragment in self.scan():
  print(fragment)