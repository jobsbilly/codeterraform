from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import bioexchange
import notebook

bio_exchange = bioexchange.BioExchangeWrapper(
  self,
  get_component("comms"),
  notebook.NotebookWrapper(get_component("notebook")),
  get_component("journal"),
)
bio_exchange.run()

# print(known_fragment_ids_around_outpost())

# def print_order(odr: BioOrderWrapper):
#   print()
#   print(odr)
#   print(f"Fragments (total needed: {odr.total_fragments_needed()}):")
#   for f in odr.fragments:
#     print(f"  {f}")
#
# all_orders = bio_exchange.orders()
# for odr in all_orders[:4]:
#   print_order(odr)

# print(bio_exchange.best_viable_order())
# print(bio_exchange.clear_order())


# print(bio_exchange._value.input.flush())

# print(f"{bio_exchange.input.connect("bio_lab_1")=}")
# print(f"{bio_exchange.input.take("st_scute_plate", 1)=}")
# print(f"{bio_exchange.input.disconnect()=}")

# print(f"{bio_exchange._value.clear_order()=}")
