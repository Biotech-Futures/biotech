"""write_time_zone_countries: the frontend's time zone to country table
(registration/timeZoneCountries.ts), written from tzdata and our countries."""
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.groups.management.commands import write_time_zone_countries as command


class WriteTimeZoneCountriesTests(SimpleTestCase):
    def test_every_country_has_its_zones_named_as_ours_does(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "timeZoneCountries.ts"
            with patch.object(command, "TARGET", target):
                call_command("write_time_zone_countries", stdout=StringIO())
            text = target.read_text(encoding="utf-8")

        self.assertIn("Australia/Sydney", text.split("'Australia': ")[1].split("\n")[0])
        # An older name a browser still reports, under its country.
        self.assertIn("Asia/Calcutta", text.split("'India': ")[1].split("\n")[0])
        # Our list's own spelling, its apostrophe escaped.
        self.assertRegex(text, r"CI: 'C.te d\\'Ivoire',")
        self.assertIn("US: 'United States of America',", text)
        # A territory's isn't a country's that shares its name.
        self.assertNotIn("Pacific/Pago_Pago", text)
        # A territory not on our list isn't put on a country that is.
        self.assertNotIn("Indian/Kerguelen", text)
