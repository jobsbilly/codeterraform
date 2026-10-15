from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import error
from status import raise_if_error
import wrapper

MIN_CREDIT_BALANCE_DEFAULT = 15000

class ShopError(error.CodeTerraformError):
  pass

class ItemNotFoundError(ShopError):
  pass

class CreditSafetyError(ShopError):
  pass

class ShopWrapper(wrapper.WrapperBase):
  _cost_by_item_id: dict[str, int] = {}

  def __init__(
      self,
      value: Shop,
      commander: Commander,
      min_credit_balance: int = MIN_CREDIT_BALANCE_DEFAULT):
    super().__init__(value, required=(commander,))
    self._value: Shop
    self._commander = commander
    self._min_credit_balance = min_credit_balance

  def _refresh_catalog(self) -> None:
    self._cost_by_item_id = {item.id: int(item.cost) for item in self._value.get_catalogue()}

  def get_cost(self, item_id: str) -> int:
    try:
      return self._cost_by_item_id[item_id]
    except KeyError:
      pass
    self._refresh_catalog()
    if (cost := self._cost_by_item_id.get(item_id, None)) is None:
      raise ItemNotFoundError(item_id)
    return cost

  def current_balance(self) -> int:
    return int(self._commander.get_credits())

  def buy(self, item_id: str, quantity: int) -> None:
    total_cost = self.get_cost(item_id) * quantity
    balance_after_purchase = self.current_balance() - total_cost
    if balance_after_purchase < self._min_credit_balance:
      raise CreditSafetyError(f"Buying {quantity} of {item_id} would cost {total_cost}, which would reduce current "
                              f"balance ({self.current_balance()} below the safety limit ({self._min_credit_balance}).")
    raise_if_error(self._value.buy(item_id, quantity), ShopError)
