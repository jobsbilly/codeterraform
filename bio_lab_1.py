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




# self: BioLab
#
# self.output.connect("inventory")
# self.output.send("st_scute_plate", 1)
# self.output.disconnect()


# print(f"{bio_lab.input.connect("inventory")=}")
# bio_lab.buy_and_load_reagents()
# print(f"{bio_lab.input.disconnect()=}")
#
#
# print(f"{bio_lab.extract()=}")

# print(f"{bio_lab.output.connect("bio_exchange_1")=}")
# print(f"{bio_lab.output.send("st_scute_plate", 1)=}")
# print(f"{bio_lab.output.disconnect()=}")


# print(f"{bio_lab.output.connect("bio_exchange_1")=}")
# print(f"{bio_lab.output.disconnect()=}")


# result = bio_lab._value.analyze()
# if result.status != "ok":
#   raise RuntimeError(result.message)
# print(result.info)
# print("Recipe:")
# for k, v in result.info.required_recipe.items():
#   print(f"  {k!r}: {v!r}")


# clock = get_component("comms")
# print("Waiting for TEST broadcast...")
# if (result := get_component("comms").wait_broadcast("TEST")).status != "ok":
#   raise RuntimeError(result.message)
# if (seconds := result.broadcast.value):
#   print(f"Sleeping for {seconds}s")
#   sleep(seconds)
#   print("ready\n")
#
# print(f"{bio_lab._value.take_from({"id": "bio_collector_1"})=}")


# print()
# print(f"{get_component("shop").buy("alkaline_buffer", 10)=}")

# clock = get_component("clock")

# print(f"{bio_lab.input.connect("inventory")=}")

# QUANTITY = 5
#
# print()
# start_tick = clock.tick()
# print(f"{bio_lab._value.input.take("alkaline_buffer", QUANTITY)=}")
# end_tick = clock.tick()
# print(f"tick duration: {end_tick - start_tick} ({start_tick=}, {end_tick=})")
#
# print()
# start_tick = clock.tick()
# print(f"{bio_lab._value.input.eject("inventory", "alkaline_buffer", QUANTITY)=}")
# end_tick = clock.tick()
# print(f"tick duration: {end_tick - start_tick} ({start_tick=}, {end_tick=})")

# print()
# print(f"{bio_lab.input.disconnect()=}")

# QUANTITY = 10
#
# print(f"{bio_lab.input.connect("inventory")=}")
# print(f"{bio_lab._value.input.take("alkaline_buffer", QUANTITY)=}")
#
# print()
# start_tick = clock.tick()
# print(f"{bio_lab._value.load("alkaline_buffer", QUANTITY)=}")
# end_tick = clock.tick() - 1
# print(f"tick duration: {end_tick - start_tick} ({start_tick=}, {end_tick=})")
#
# print()
# print(f"{bio_lab.unload_reagents()=}")
# print(f"{bio_lab.output.connect("inventory")=}")
# print(f"{bio_lab.output.send("alkaline_buffer", QUANTITY)=}")
# print(f"{bio_lab.output.disconnect()=}")
# print(f"{bio_lab.input.disconnect()=}")
