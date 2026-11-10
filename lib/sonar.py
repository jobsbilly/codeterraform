from __builtins__ import *  # Just to make PyCharm... less grumpy; it's never happy.

from typing import Callable, Iterable

from error import CodeTerraformError, raise_if_none
from notebook import NotebookWrapper
from status import assign_or_raise, raise_if_error


UNRESOLVED_CONTACTS_KEY = "unresolved_sonar_contacts_by_point"

_TOTAL_POI_COUNT = 115
_BLOCKED_CONTACT_REASONS = {"too_hard", "tier_too_low", "research_required", "wrong_scanner"}
_PETROLEUM_SURVEY_ID = "research_petroleum_survey"
_ADVANCED_OIL_EXTRACTION_ID = "research_advanced_oil_extraction"
_RESEARCH_IDS = {
  "research_geological_survey",
  "research_hydrology_survey",
  _PETROLEUM_SURVEY_ID,
  _ADVANCED_OIL_EXTRACTION_ID,
  "research_exotic_husbandry",
  "research_deep_exotics",
}

def point_key(poi_or_site: PointOfInterest | Site | BlockedContact) -> str:
  return repr([poi_or_site.x, poi_or_site.y])

def is_fully_resolved(site: Site | None) -> bool:
  # noinspection bad-argument-type,calling-non-callable
  return (site is not None
          and getattr(site, "seismic_status", "N/A") in ("dry", "N/A")  # "potential" means a survey is still needed.
          and getattr(site, "survey_level", lambda: "N/A")() in ("deep", "seismic", "N/A"))

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

  if notebook.get(UNRESOLVED_CONTACTS_KEY, None) is not None:
    return
  print(f"{UNRESOLVED_CONTACTS_KEY!r} table not found in Data Archive; populating now...")

  sites_by_point = {point_key(site): site for site in journal.surveyed_sites(planet.id)}
  table_json = {}
  fully_resolved_count = 0
  for poi in pois:
    key = point_key(poi)
    if not poi.scanned or not is_fully_resolved(sites_by_point.get(key, None)):
      table_json[key] = {"sonar_tier": None, "missing_research_ids": None, "reason": None, "message": None}
    else:
      fully_resolved_count += 1
  raise_if_error(notebook.transaction(UNRESOLVED_CONTACTS_KEY, None, _tx_populate_table_if_not_exists(table_json)))
  print(f"Populated {len(table_json)} unresolved contacts after ignoring {fully_resolved_count} fully-resolved sites.")

def missing_research_ids(research: Research) -> list[str]:
  return [_id for _id in _RESEARCH_IDS if not research.is_unlocked(_id)]

def _make_unresolved_contact(tier: str, missing_research: list[str], reason: str, message: str) -> JsonValue:
  return {
    "sonar_tier": tier,
    "missing_research_ids": missing_research,
    "reason": reason,
    "message": message,
  }

def _from_unresolved_survey(site: Site, tier: str, missing_research: list[str]) -> JsonValue:
  site_kind = site.kind()
  # I *think* all other cases should just show up in the scan's blocked sites (and thus not flow through this function).
  if site_kind == "inert":
    if any(_id in missing_research for _id in (_PETROLEUM_SURVEY_ID, _ADVANCED_OIL_EXTRACTION_ID)):
      return _make_unresolved_contact(
        tier=tier,
        missing_research=missing_research,
        reason="research_required",
        message=(f"Inert sites require both {_PETROLEUM_SURVEY_ID!r} and {_ADVANCED_OIL_EXTRACTION_ID!r} to reveal any "
                 "deep oil wells."),
      )
    if tier != "seismic":
      return _make_unresolved_contact(
        tier=tier,
        missing_research=missing_research,
        reason="tier_too_low",
        message="Inert sites require Seismic-tier sonar to reveal any deep oil wells.",
      )
  if site_kind in ("thermal", "exotic") and tier not in ("deep", "seismic"):
    return _make_unresolved_contact(
      tier=tier,
      missing_research=missing_research,
      reason="tier_too_low",
      message=f"{site_kind.capitalize()} sites require Deep- or Seismic-tier sonar to fully resolve.",
    )
  raise CodeTerraformError(f"Unable to determine why surveyed site is unresolved: {site!r}")

def _update_unresolved_contacts(
    tier: str,
    missing_research: list[str],
    blocked: Iterable[BlockedContact],
    unresolved_surveys_by_point_key: dict[str, Site],
    newly_resolved_point_keys: Iterable[str],
    notebook: NotebookWrapper,
) -> None:
  unresolved_contacts_by_point = {point_key(b): _make_unresolved_contact(tier, missing_research, b.reason, b.message)
                                  for b in blocked}
  for key, site in unresolved_surveys_by_point_key.items():
    unresolved_contacts_by_point[key] = _from_unresolved_survey(site, tier, missing_research)
  def tx_fn(table: dict[str, JsonValue]) -> dict[str, JsonValue]:
    for key, value in unresolved_contacts_by_point.items():
      if key not in table:
        raise CodeTerraformError(f"Update aborted; the site at {key} was previously resolved, but attempted to update "
                                 f"with {value=}")
      table[key] = value
    for key in newly_resolved_point_keys:
      if key not in table:
        warn(f"Newly-resolved site at {key} was not found in {UNRESOLVED_CONTACTS_KEY!r} table.")
        continue
      del table[key]
    return table
  raise_if_error(notebook.transaction(UNRESOLVED_CONTACTS_KEY, None, tx_fn))

def scan_and_survey(sonar: SonarModule, notebook: NotebookWrapper, research: Research) -> None:
  if (scan_result := raise_if_error(sonar.scan(), ignore=_BLOCKED_CONTACT_REASONS)).status in _BLOCKED_CONTACT_REASONS:
    debug(f"Scan result was {scan_result.status!r} with message: {scan_result.message!r}")

  existing_unresolved_contacts_by_point = raise_if_none(notebook.get(UNRESOLVED_CONTACTS_KEY))

  newly_resolved_point_keys = []
  unresolved_surveys_by_point_key = {}
  for scanned_site in scan_result.sites:
    key = point_key(scanned_site)
    if key not in existing_unresolved_contacts_by_point:
      continue  # Already resolved.
    surveyed_site: Site = assign_or_raise(sonar.survey(scanned_site))
    if is_fully_resolved(surveyed_site):
      newly_resolved_point_keys.append(key)
    else:
      unresolved_surveys_by_point_key[key] = surveyed_site
  if scan_result.blocked or newly_resolved_point_keys or unresolved_surveys_by_point_key:
    _update_unresolved_contacts(sonar.tier(), missing_research_ids(research), scan_result.blocked,
                                unresolved_surveys_by_point_key, newly_resolved_point_keys, notebook)
  if newly_resolved_point_keys:
    print(f"Fully resolved {len(newly_resolved_point_keys)} site(s): {newly_resolved_point_keys}")
