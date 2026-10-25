from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import bioluminizer
from error import raise_if_none
import notebook
import signalbus

bio_luminizer = bioluminizer.BioLuminizerWrapper(
  self,
  signalbus.CommsWrapper(raise_if_none(get_component("comms"))),
  notebook.NotebookWrapper(raise_if_none(get_component("notebook"))),
)
bio_luminizer.run()
# bio_luminizer.run_single_iteration()
