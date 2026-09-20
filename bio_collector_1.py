from __builtins__ import *

from typing import Literal

TaskType = Literal["order", "fetch unidentified fragments", "wait"]

def next_task() -> TaskType:
  pass

def work_on_order():
  pass

def fetch_unidentified_fragment():
  pass

# biome = self.outpost.biome

while True:
  # Check if self.cargo has stuff in it.
  # TODO: Figure out what to do with unexpectedly-occupied cargo.

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

print(f"{self.type_id=}")

for fragment in self.scan():
  print(fragment)