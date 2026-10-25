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

  def current_balance(self) -> int:
    return int(self._commander.get_credits())

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

  def total_cost(self, count_by_item_id: dict[str, int]) -> int:
    return int(sum(self.get_cost(item_id) * count for item_id, count in count_by_item_id.items()))

  def can_afford(self, count_by_item_id: dict[str, int]) -> bool:
    return self.current_balance() - self.total_cost(count_by_item_id) >= self._min_credit_balance

  def buy_all(self, count_by_item_id: dict[str, int]) -> None:
    if not self.can_afford(count_by_item_id):
      raise CreditSafetyError(f"Aborted: total cost ({self.total_cost(count_by_item_id)}) would reduce the current "
                              f"balance below the configured minimum ({self._min_required_balance}); order: "
                              f"{count_by_item_id}")
    for item_id, count in count_by_item_id.items():
      raise_if_error(self._value.buy(item_id, count), ShopError)

  def buy(self, item_id: str, quantity: int) -> None:
    self.buy_all({item_id: quantity})
