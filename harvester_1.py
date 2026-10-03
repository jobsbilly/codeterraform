import harvester as harvesterlib
import shop

harvester = harvesterlib.HarvesterWrapper(
  self,
  get_component("scanner_1"),
  shop.ShopWrapper(get_component("shop"), get_component("commander")),
  get_component("clock"),
)
harvester.run()
