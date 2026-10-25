from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

from error import raise_if_none
import notebook
import pioneer as pioneerlib
import signalbus


pioneer = pioneerlib.CourierPioneerWrapper(
  self,
  raise_if_none(get_component("clock")),
  raise_if_none(get_component("outpost_network")),
  signalbus.CommsWrapper(raise_if_none(get_component("comms"))),
  notebook.NotebookWrapper(raise_if_none(get_component("notebook"))),
)
pioneer.run()

# pioneer = pioneerlib.PioneerWrapper(self, get_component("clock"), get_component("outpost_network"))
# pioneer = pioneerlib.PioneerWrapper(self)



# pioneer.load("outpost_kit")
# goto((-330, 130))
# goto((220, 100))
# print(pioneer._value.constructor.execute("outpost_blueprint_2"))
# pioneer.survey_sites_in_range()
# goto((0, 0))



# pioneer.survey_sites_in_range()

