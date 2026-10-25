from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

from error import CodeTerraformError, raise_if_none
import notebook as notebooklib
import signalbus
from status import assign_or_raise, raise_if_error
from workorders import BioWorkOrder
import wrapper


_COLORS = ("red", "green", "blue")


class BioLuminizerWrapper(wrapper.MachineWrapper):
  def __init__(self, value: BioLuminizer, comms: signalbus.CommsWrapper, notebook: notebooklib.NotebookWrapper):
    super().__init__(value, required=(comms, notebook))
    self._value: BioLuminizer
    self._comms = (comms
                   .register(BioWorkOrder.Channel.EXTRACTED_SAMPLES, outpost=self._value.outpost.id)
                   .register(BioWorkOrder.Channel.PREPARED_SAMPLES, outpost=self._value.outpost.id))
    self._notebook = notebook

  def _block_until_sample_arrives(self) -> BioWorkOrder:
    work_order = BioWorkOrder.from_comms_message(
      assign_or_raise(self._comms.wait(BioWorkOrder.Channel.EXTRACTED_SAMPLES)))

    # Persist the work order while working on it.
    raise_if_error(work_order.claim(self.id, self._notebook))

    return work_order

  def _take_sample(self, fragment_id: str, lab: str) -> None:
    raise_if_error(self.input.connect(lab))
    # TODO: move this (and other near-identical logic) to some kind of reusable retry function or decorator.
    for _ in range(5):
      if (result := self.input.take(fragment_id, 1)).status != "busy":
        break
      sleep(0.25)  # Time it takes auto feeders to transfer 1 item.
    raise_if_error(result)

  def _luminize(self, target_glow: list[int]) -> None:
    target_delta_by_color = {}
    # How much a brightness step impacts the sample's glow.
    step_delta_by_effect_color_by_lamp_color = {}
    # Steps that would be needed to get a color to its target_glow IF lamp colors were pure (i.e., didn't bleed).
    max_steps_by_color = {}
    for i, color in enumerate(_COLORS):
      target_delta_by_color[color] = target_glow[i] - self.chamber.glow[i]
      step_delta_by_effect_color_by_lamp_color[color] = {
        _COLORS[j]: step_delta for j, step_delta in enumerate(self.lamp_signature(color))}
      max_steps_by_color[color] = floor(target_delta_by_color[color]
                                        / step_delta_by_effect_color_by_lamp_color[color][color])

    # Steps that would be needed to get a color to its target_glow IF both other lamp colors used their max_steps.
    min_steps_by_color = {}
    for color in _COLORS:
      delta_from_other_lamps_bleeding = sum(step_delta_by_effect_color_by_lamp_color[lamp][color] * max_steps
                                            for lamp, max_steps in max_steps_by_color.items()
                                            if lamp != color)
      min_steps_by_color[color] = ceil((target_delta_by_color[color] - delta_from_other_lamps_bleeding)
                                       / step_delta_by_effect_color_by_lamp_color[color][color])

    for lamp_steps in product(*[range(min_steps_by_color[color], max_steps_by_color[color] + 1) for color in _COLORS]):
      raise_if_error(self.set_lamps(*lamp_steps))
      if self.glow() == target_glow:
        raise_if_error(self.infuse())
        return
    raise CodeTerraformError(f"No solution found to get from {self.chamber.glow=} to {target_glow=}")

  def _prepare_for_main_loop(self) -> None:
    work_order = BioWorkOrder.get_claimed(self.id, self._notebook)
    if work_order is None:
      if self.chamber is not None:
        raise CodeTerraformError("Found a sample without a work order during startup.")
      if self.input.count() > 0:
        raise CodeTerraformError("Found a non-empty input buffer without a work order during startup.")
      return

    self._main_loop_iteration(work_order)

  def _main_loop_iteration(self, existing_work_order: BioWorkOrder | None = None) -> bool:
    work_order: BioWorkOrder = existing_work_order or self._block_until_sample_arrives()

    if not self.chamber:
      if self.input.count() == 0:
        self._take_sample(raise_if_none(work_order.fragment), raise_if_none(work_order.lab))
      raise_if_error(self.load(work_order.fragment))

    self._luminize(raise_if_none(work_order.glow))

    work_order.luminizer = self.id
    raise_if_error(self._comms.send(BioWorkOrder.Channel.PREPARED_SAMPLES, work_order.to_json()))

    raise_if_error(work_order.release(self.id, self._notebook))

    # TODO: Shutdown (by returning False) when all orders in the biome have been completed.
    return True
