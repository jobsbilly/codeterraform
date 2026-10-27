from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import bioexchange
from error import raise_if_none
import notebook
import signalbus

bio_exchange = bioexchange.BioExchangeWrapper(
  self,
  signalbus.CommsWrapper(raise_if_none(get_component("comms"))),
  notebook.NotebookWrapper(raise_if_none(get_component("notebook"))),
  raise_if_none(get_component("journal")),
)
bio_exchange.run()
# bio_exchange.run_single_iteration()
