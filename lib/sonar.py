from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

import dataclasses
import enum
from typing import Callable, Iterable, Self

from error import CodeTerraformError, raise_if_none
from notebook import NotebookWrapper
from status import assign_or_raise, raise_if_error


UNRESOLVED_CONTACTS_KEY = "unresolved_contact_by_point_str"

_TOTAL_POI_COUNT = 115


class _ResearchId(enum.StrEnum):
  GEOLOGICAL_SURVEY = "research_geological_survey"
  HYDROLOGY_SURVEY = "research_hydrology_survey"
  PETROLEUM_SURVEY = "research_petroleum_survey"
  ADVANCED_OIL_EXTRACTION = "research_advanced_oil_extraction"
  EXOTIC_FLUIDS = "research_exotic_husbandry"
  DEEP_EXOTICS = "research_deep_exotics"


class SonarTier(enum.StrEnum):
  BASIC = "basic"
  WIDE = "wide"
  DEEP = "deep"
  SEISMIC = "seismic"

  def is_better_than(self, other: str) -> bool:
    if other in (SonarTier.SEISMIC, self):
      return False
    # Whichever is encountered first is lower-tier (ties are handled above).
    for member in SonarTier:
      if member in (self, other):
        return member == other
    raise RuntimeError("Impossible: neither self nor other was a SonarTier member (both should be, always)")


class _Reason(enum.StrEnum):
  NEVER_SCANNED = "never_scanned"
  WRONG_SCANNER = "wrong_scanner"
  TOO_HARD = "too_hard"
  TIER_TOO_LOW = "tier_too_low"
  RESEARCH_REQUIRED = "research_required"


class SiteKind(enum.StrEnum):
  UNKNOWN = "unknown"
  MINERAL = "mineral"
  THERMAL = "thermal"
  WATER = "water"
  OIL = "oil"
  EXOTIC = "exotic"
  INERT = "inert"


def get_point_str(location: PointOfInterest | Site | BlockedContact) -> str:
  return repr([location.x, location.y])

def from_point_str(value: str) -> list[float]:
  return list(map(int, value.strip("[]").split(",")))

def _required_research(site_kind: str, last_locked_research: Iterable[str]) -> set[_ResearchId]:
  if site_kind == SiteKind.INERT:
    return {_ResearchId.PETROLEUM_SURVEY, _ResearchId.ADVANCED_OIL_EXTRACTION}
  if site_kind == SiteKind.UNKNOWN:
    return {
      _ResearchId.GEOLOGICAL_SURVEY,
      _ResearchId.HYDROLOGY_SURVEY,
      _ResearchId.PETROLEUM_SURVEY,
      # Only require DEEP_EXOTICS when EXOTIC_FLUIDS was already tried (since only rare deposits require the former).
      _ResearchId.EXOTIC_FLUIDS if _ResearchId.EXOTIC_FLUIDS in last_locked_research else _ResearchId.DEEP_EXOTICS,
    }
  # All other site kinds remain UNKNOWN until all required research is already unlocked.
  return set()

def _required_locked_research(
    site_kind: str,
    locked_research: Iterable[str],
    last_locked_research: Iterable[str],
) -> list[str]:
  return [_id.value for _id in _required_research(site_kind, last_locked_research).difference(locked_research)]

def _annotate(message: str, required_locked_research: Iterable[str]) -> str:
  if required_locked_research:
    return f"{message}; scan again after unlocking any of: {", ".join(required_locked_research)}."
  return message


@dataclasses.dataclass
class UnresolvedContact:
  kind: str | SiteKind
  tier: str | SonarTier
  locked_research: list[str]
  reason: str | _Reason
  message: str

  def to_json(self) -> dict[str, JsonValue]:
    return dataclasses.asdict(self)

  def should_scan(self, current_tier: SonarTier, current_locked_research: set[_ResearchId]) -> bool:
    if self.reason == _Reason.NEVER_SCANNED:
      return True
    if self.reason == _Reason.WRONG_SCANNER:
      return False  # Needs bio scanner.
    if self.reason == _Reason.RESEARCH_REQUIRED:
      # Scan if any required research from the last scan has been unlocked since then.
      if not (last_scan_required_research := _required_research(self.kind, self.locked_research)):
        raise CodeTerraformError(f"Research blocked this site on the last scan, but no required research found")
      unlocked_since_last_scan = set(self.locked_research).difference(current_locked_research)
      return not unlocked_since_last_scan.isdisjoint(last_scan_required_research)
    if self.reason in (_Reason.TIER_TOO_LOW, _Reason.TOO_HARD):
      return current_tier.is_better_than(self.tier)
    raise CodeTerraformError(f"Unrecognized UnresolvedContact.reason={self.reason!r}")

  @classmethod
  def from_json(cls, value: dict[str, JsonValue]) -> Self:
    return cls(**value)

  @classmethod
  def _never_scanned(cls, kind: str, locked_research: list[str]) -> Self:
    return cls(
      kind=kind,
      tier=None,  # type: ignore[bad-argument-type]
      locked_research=locked_research,
      reason=_Reason.NEVER_SCANNED,
      message="No attempts to scan have been recorded."
    )

  @classmethod
  def from_blocked(
      cls,
      blocked: BlockedContact,
      tier: str,
      locked_research: list[str],
      last_locked_research: Iterable[str],
  ) -> Self:
    return cls(
      kind=SiteKind.UNKNOWN,
      tier=tier,
      locked_research=locked_research,
      reason=blocked.reason,
      message=_annotate(blocked.message,
                        _required_locked_research(SiteKind.UNKNOWN, locked_research, last_locked_research)),
    )

  @classmethod
  def from_unresolved_survey(
      cls,
      site: Site,
      tier: str,
      locked_research: list[str],
      last_locked_research: Iterable[str],
  ) -> Self:
    site_kind: str = site.kind()
    if required_locked_research := _required_locked_research(site_kind, locked_research, last_locked_research):
      return cls(
        kind=site_kind,
        tier=tier,
        locked_research=locked_research,
        reason=_Reason.RESEARCH_REQUIRED,
        message=_annotate("Missing required research", required_locked_research),
      )
    if site_kind in (SiteKind.INERT, SiteKind.THERMAL, SiteKind.EXOTIC):
      required_tiers = (SonarTier.SEISMIC,) if site_kind == SiteKind.INERT else (SonarTier.DEEP, SonarTier.SEISMIC)
      if tier not in required_tiers:
        return cls(
          kind=site_kind,
          tier=tier,
          locked_research=locked_research,
          reason=_Reason.TIER_TOO_LOW,
          message=f"Sonar tier is too low; scan again after upgrading to any of: {", ".join(required_tiers)}",
        )
    raise CodeTerraformError(f"Unable to determine why surveyed site is unresolved: {site!r}")


def is_fully_resolved(site: Site | None) -> bool:
  # noinspection bad-argument-type,calling-non-callable
  return (site is not None
          and getattr(site, "seismic_status", "N/A") in ("dry", "N/A")  # "potential" means a survey is still needed.
          and getattr(site, "survey_level", lambda: "N/A")() in (SonarTier.DEEP, SonarTier.SEISMIC, "N/A"))

def _tx_populate_table_if_not_exists(value_to_populate: JsonValue) -> Callable[[JsonValue], JsonValue]:
  def fn(existing_value: JsonValue) -> JsonValue:
    if existing_value is not None:
      debug("Aborted; the table was populated elsewhere between the existence check and attempting the transaction.")
      return existing_value
    return value_to_populate
  return fn

def populate_table_if_not_exists(notebook: NotebookWrapper, planet: Nocturna, journal: Journal) -> None:
  # TODO: add support for populating new-to-the-game PointOfInterests.
  pois = planet.points_of_interest()
  # noinspection unsupported-operator
  if len(pois) != _TOTAL_POI_COUNT:
    raise CodeTerraformError("Time to add support for populating new-to-the-game PointOfInterests")

  if notebook.has(UNRESOLVED_CONTACTS_KEY):
    return
  print(f"{UNRESOLVED_CONTACTS_KEY!r} table not found in Data Archive; populating now...")

  all_research_ids = [_id.value for _id in _ResearchId]
  surveyed_site_by_point = {get_point_str(site): site for site in journal.surveyed_sites(planet.id)}
  table_json = {}
  fully_resolved_count = 0
  for poi in pois:
    key = get_point_str(poi)
    if not poi.scanned or not is_fully_resolved(surveyed_site_by_point.get(key, None)):
      # noinspection protected-member
      table_json[key] = UnresolvedContact._never_scanned(poi.kind, all_research_ids).to_json()
    else:
      fully_resolved_count += 1
  raise_if_error(notebook.transaction(UNRESOLVED_CONTACTS_KEY, None, _tx_populate_table_if_not_exists(table_json)))
  print(f"Populated {len(table_json)} unresolved contacts after ignoring {fully_resolved_count} fully-resolved sites.")

def _update_unresolved_contacts(
    unresolved_contact_by_point_str: dict[str, UnresolvedContact],
    newly_resolved_point_strs: Iterable[str],
    notebook: NotebookWrapper,
) -> None:
  def tx_fn(table: dict[str, JsonValue]) -> dict[str, JsonValue]:
    for key, value in unresolved_contact_by_point_str.items():
      if key not in table:
        raise CodeTerraformError(f"Update aborted; the site at {key} was previously resolved, but attempted to update "
                                 f"with {value=}")
      table[key] = value.to_json()
    for key in newly_resolved_point_strs:
      if key not in table:
        warn(f"Newly-resolved site at {key} was not found in {UNRESOLVED_CONTACTS_KEY!r} table.")
        continue
      del table[key]
    return table
  raise_if_error(notebook.transaction(UNRESOLVED_CONTACTS_KEY, None, tx_fn))

def get_unresolved_contact_by_point_str(notebook: NotebookWrapper) -> dict[str, UnresolvedContact]:
  return {k: UnresolvedContact.from_json(v) for k, v in  raise_if_none(notebook.get(UNRESOLVED_CONTACTS_KEY)).items()}

def _get_locked(research: Research) -> list[str]:
  return [_id.value for _id in _ResearchId if not research.is_unlocked(_id.value)]

def scan_and_survey(sonar: SonarModule, notebook: NotebookWrapper, research: Research) -> None:
  if (scan_result := raise_if_error(sonar.scan(), ignore=_Reason)).status in _Reason:
    debug(f"Scan result was {scan_result.status!r} with message: {scan_result.message!r}")

  tier = sonar.tier()
  locked_research = _get_locked(research)
  last_locked_research_by_point_str = {k: v.locked_research
                                       for k, v in get_unresolved_contact_by_point_str(notebook).items()}
  unresolved_contact_by_point_str = {}
  for blocked in scan_result.blocked:
    key = get_point_str(blocked)
    unresolved_contact_by_point_str[key] = UnresolvedContact.from_blocked(blocked, tier, locked_research,
                                                                          last_locked_research_by_point_str[key])

  newly_resolved_point_strs = []
  for scanned_site in scan_result.sites:
    key = get_point_str(scanned_site)
    if (last_locked_research := last_locked_research_by_point_str.get(key, None)) is None:
      continue  # Already fully resolved.
    surveyed_site: Site = assign_or_raise(sonar.survey(scanned_site))
    if is_fully_resolved(surveyed_site):
      newly_resolved_point_strs.append(key)
    else:
      unresolved_contact_by_point_str[key] = UnresolvedContact.from_unresolved_survey(
        surveyed_site, tier, locked_research, last_locked_research)
  if unresolved_contact_by_point_str or newly_resolved_point_strs:
    _update_unresolved_contacts(unresolved_contact_by_point_str, newly_resolved_point_strs, notebook)
  if newly_resolved_point_strs:
    count = len(newly_resolved_point_strs)
    print(f"Fully resolved {count} site{"s" if count > 1 else ""}.")

def resolvable_contact_points(notebook: NotebookWrapper, sonar_tier: str, research: Research) -> list[list[float]]:
  tier = SonarTier(sonar_tier)
  locked_research = {_ResearchId(_id) for _id in _get_locked(research)}
  return [from_point_str(point_str)
          for point_str, contact in get_unresolved_contact_by_point_str(notebook).items()
          if contact.should_scan(tier, locked_research)]

def all_contacts_resolved(notebook: NotebookWrapper) -> bool:
  # TODO: Add Bio-scanner support.
  return not any(contact.reason != _Reason.WRONG_SCANNER
                 for contact in get_unresolved_contact_by_point_str(notebook).values())
