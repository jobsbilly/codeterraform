from __builtins__ import get_component

from error import raise_if_none
import solar

solar.SolarGeneratorWrapper(self, raise_if_none(get_component("clock"))).run()
