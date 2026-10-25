from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import biolab
from error import raise_if_none
import notebook
import shop
import signalbus

bio_lab = biolab.BioLabWrapper(
  self,
  signalbus.CommsWrapper(raise_if_none(get_component("comms"))),
  notebook.NotebookWrapper(raise_if_none(get_component("notebook"))),
  shop.ShopWrapper(raise_if_none(get_component("shop")), raise_if_none(get_component("commander"))),
)
bio_lab.run()
# bio_lab.run_single_iteration()
