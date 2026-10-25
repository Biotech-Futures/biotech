"""Write frontend/src/registration/timeZoneCountries.ts: each time zone's
country, as our country list names it, for a sign-up's Country to start on
(registration/detectPlace.ts). From the IANA time zone tables tzdata carries
(zone.tab and iso3166.tab) and the countries migration 0012 loads. Run again
when either changes:

    python manage.py write_time_zone_countries
"""
import ast
import os
import unicodedata
from pathlib import Path

import tzdata
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

ZONEINFO = Path(os.path.dirname(tzdata.__file__)) / "zoneinfo"
MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "0012_load_countries.py"
TARGET = Path(settings.BASE_DIR).parent / "frontend" / "src" / "registration" / "timeZoneCountries.ts"

# The tables' names that aren't ours as they stand (Eswatini's is matched below).
ALIASES = {
    "KR": "South Korea", "KP": "North Korea", "RU": "Russia", "VN": "Vietnam", "LA": "Laos",
    "SY": "Syria", "IR": "Iran", "TZ": "Tanzania", "BO": "Bolivia", "VE": "Venezuela", "MD": "Moldova",
    "BN": "Brunei", "CZ": "Czechia (Czech Republic)", "CG": "Congo (Congo-Brazzaville)",
    "CD": "Democratic Republic of the Congo", "CI": "Côte d'Ivoire", "MM": "Myanmar (formerly Burma)",
    "PS": "Palestine State", "VA": "Holy See", "FM": "Micronesia", "TR": "Turkey",
    "GB": "United Kingdom", "US": "United States of America", "CF": "Central African Republic",
    "CV": "Cabo Verde", "TL": "Timor-Leste", "ST": "Sao Tome and Principe", "KN": "Saint Kitts and Nevis",
    "LC": "Saint Lucia", "VC": "Saint Vincent and the Grenadines", "MK": "North Macedonia",
    "BS": "Bahamas", "GM": "Gambia", "WS": "Samoa",
}
# Folders of zones that aren't anywhere's.
SKIP = {"Etc", "posix", "right", "SystemV"}


def _key(name, *, drop_brackets=False):
    """A name to compare by: no accents, case or punctuation; our names
    without their "(formerly …)", but not the tables' ("Samoa (American)")."""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = name.lower().replace("&", "and")
    if drop_brackets:
        name = name.split("(")[0]
    return "".join(ch for ch in name if ch.isalnum())


def _js(value):
    """A single-quoted JavaScript string."""
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _rows(table):
    for line in (ZONEINFO / table).read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            yield line.split("\t")


class Command(BaseCommand):
    help = "Write the frontend's time zone to country table (registration/timeZoneCountries.ts)."

    def handle(self, *args, **options):
        tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
        countries = next(
            ast.literal_eval(node.value) for node in tree.body
            if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "COUNTRIES"
        )
        ours = {_key(name, drop_brackets=True): name for name in countries}
        aliases = {**ALIASES, "SZ": next(name for name in countries if name.startswith("Eswatini"))}

        codes = {}
        for code, name, *_ in _rows("iso3166.tab"):
            if code in aliases:
                codes[code] = aliases[code]
            elif _key(name) in ours:
                codes[code] = ours[_key(name)]
        missing = sorted(set(countries) - set(codes.values()))
        if missing:
            raise CommandError(f"No country code for: {', '.join(missing)}. Add them to ALIASES.")

        zones, listed = {}, set()
        for code, _, zone, *_ in _rows("zone.tab"):
            listed.add(zone)
            if code in codes:
                zones[zone] = codes[code]
        # Older names browsers still report (Asia/Calcutta, Australia/ACT): a
        # copy of a listed zone under another name, when the zones it copies
        # are all one country's. A zone the table lists is its own country's.
        by_content = {}
        for zone, country in list(zones.items()):
            by_content.setdefault((ZONEINFO / zone).read_bytes(), set()).add(country)
        for path in ZONEINFO.rglob("*"):
            if not path.is_file() or "." in path.name:
                continue
            name = path.relative_to(ZONEINFO).as_posix()
            if name in listed or "/" not in name or name.split("/")[0] in SKIP:
                continue
            owners = by_content.get(path.read_bytes())
            if owners and len(owners) == 1:
                zones[name] = next(iter(owners))

        grouped = {}
        for zone, country in sorted(zones.items()):
            grouped.setdefault(country, []).append(zone)
        lines = [
            "/**",
            " * Each time zone's country, as our country list names it (migration",
            " * 0012_load_countries), with the older names browsers still report",
            " * (Asia/Calcutta, Australia/ACT); and each country code's, for a browser",
            " * language's region (en-AU). Written by the backend's",
            " * `python manage.py write_time_zone_countries`: don't edit by hand.",
            " */",
            "",
            "/** Each of our countries' time zones. */",
            "export const COUNTRY_TIME_ZONES: Record<string, string> = {",
            *(f"  {_js(country)}: {_js(' '.join(names))}," for country, names in sorted(grouped.items())),
            "}",
            "",
            "/** Each country code's country, as ours names it. */",
            "export const CODE_COUNTRIES: Record<string, string> = {",
            *(f"  {code}: {_js(name)}," for code, name in sorted(codes.items())),
            "}",
            "",
        ]
        TARGET.write_text("\n".join(lines), encoding="utf-8")
        self.stdout.write(f"Wrote {len(zones)} time zones for {len(grouped)} countries to {TARGET}.")
