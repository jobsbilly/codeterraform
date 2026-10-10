from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

from error import raise_if_error

charging_station: ChargingStation = self


# print(charging_station.charge("pioneer_1"))



# print(f"{charging_station.dispatch_rescue("pioneer_1", 0.3)}")


# print(f"{charging_station.cancel_rescue()}")


while True:
  for vehicle_id in charging_station.get_docked():
    raise_if_error(charging_station.charge(vehicle_id), ignore=["queued", "charging", "target_reached"])

  sleep(1)

