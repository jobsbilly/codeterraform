from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import dnasequencer
from error import raise_if_none
import notebook
import signalbus

dna_sequencer = dnasequencer.DNASequencerWrapper(
  self,
  signalbus.CommsWrapper(raise_if_none(get_component("comms"))),
  notebook.NotebookWrapper(raise_if_none(get_component("notebook"))),
)
dna_sequencer.run()
# dna_sequencer.run_single_iteration()
