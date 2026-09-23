from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import wrapper

print(f"Starting up: {self.id!r}")

class BioLabWrapper(wrapper.WrapperBase):
  def __init__(self, value: BioLab):
    super().__init__(value)
    self._value: BioLab

  def _prepare_for_main_loop(self) -> None:
    raise NotImplementedError()

  # TODO: rename this to something less silly.
  def _do_loopy_things(self) -> None:
    raise NotImplementedError()

  def run(self) -> None:
    self._prepare_for_main_loop()
    while True:
      self._do_loopy_things()


# TODO: find a way to broadcast when a new fragment_id has been analyzed.
#       Maybe fetch catalogued fragments right before each analysis?

bio_lab = BioLabWrapper(self)

while True:
  # if (specimen := bio_lab._value.specimen) is not None:
  #   blah = specimen.stage


  # Is the lab already busy analyzing or extracting?
  # Is there already a specimen in the chamber?
  # Does it need to be analyzed?
  # Are reagents loaded?
  # Does it have somewhere to go (or, if no specimen, is the output occupied)?

  break  # TODO: delete this line when script is complete.
