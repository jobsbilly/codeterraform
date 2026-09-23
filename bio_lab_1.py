from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import error
import wrapper

print(f"Starting up: {self.id!r}")

# TODO: Replace hardcoded channel name with pseudo-enum.
COLLECTED_FRAGMENTS_CHANNEL = "collected_fragments"

class BioLabError(error.CodeTerraformError):
  pass

class BioLabWrapper(wrapper.WrapperBase):
  def __init__(self, value: BioLab, comms: Comms):
    if comms is None:
      raise TypeError("`comms` cannot be None")
    super().__init__(value)
    self._value: BioLab
    self._comms = comms

  def _prepare_for_main_loop(self) -> None:
    raise NotImplementedError()

  # TODO: rename this to something less silly.
  def _do_loopy_things(self) -> None:
    # Wait for a collector's signal to take its fragment.
    if (result := self._comms.wait(COLLECTED_FRAGMENTS_CHANNEL)).status != "ok":
      raise BioLabError(result.message)
    # Take the collector's fragment.
    work_order_packet = result.packet
    if (result := self._value.take_from({"id": work_order_packet.sender})).status != "ok":
      raise BioLabError(result.message)

  def run(self) -> None:
    self._prepare_for_main_loop()
    while True:
      self._do_loopy_things()


# TODO: find a way to broadcast when a new fragment_id has been analyzed.
#       Maybe fetch catalogued fragments right before each analysis?

bio_lab = BioLabWrapper(self, get_component("comms"))

while True:
  # if (specimen := bio_lab._value.specimen) is not None:
  #   blah = specimen.stage


  # Is the lab already busy analyzing or extracting?
  # Is there already a specimen in the chamber?
  # Does it need to be analyzed?
  # Are reagents loaded?
  # Does it have somewhere to go (or, if no specimen, is the output occupied)?

  break  # TODO: delete this line when script is complete.
