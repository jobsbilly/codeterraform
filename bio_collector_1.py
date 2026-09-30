from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import biocollector
import notebook

bio_collector = biocollector.BioCollectorWrapper(
  self,
  get_component("comms"),
  notebook.NotebookWrapper(get_component("notebook")),
)
bio_collector.run()
