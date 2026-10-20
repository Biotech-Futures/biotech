"""The registration form's country and state dropdowns: as the database holds
them, open to anyone (registration is)."""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.groups.models import Countries, CountryStates

URL = "/api/v1/registration/states/"


class RegistrationStatesTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.australia, _ = Countries.objects.get_or_create(country_name="Australia")
        for name in ("VIC", "ACT", "NSW"):
            CountryStates.objects.get_or_create(country=self.australia, state_name=name)
        other, _ = Countries.objects.get_or_create(country_name="New Zealand")
        CountryStates.objects.get_or_create(country=other, state_name="Otago")

    def test_lists_the_countrys_states_from_the_database_in_order(self):
        response = self.client.get(URL, {"country": "australia"})
        self.assertEqual(response.status_code, 200)
        states = response.json()["states"]
        expected = list(
            CountryStates.objects.filter(country=self.australia)
            .order_by("state_name")
            .values_list("state_name", flat=True)
        )
        self.assertEqual(states, expected)
        self.assertIn("ACT", states)
        self.assertNotIn("Otago", states)

    def test_none_for_no_country_or_one_without_states(self):
        self.assertEqual(self.client.get(URL).json(), {"states": []})
        self.assertEqual(self.client.get(URL, {"country": "Atlantis"}).json(), {"states": []})


class RegistrationCountriesTests(TestCase):
    def test_lists_every_country_from_the_database_in_order(self):
        Countries.objects.get_or_create(country_name="New Zealand")
        Countries.objects.get_or_create(country_name="Australia")
        response = APIClient().get("/api/v1/registration/countries/")
        self.assertEqual(response.status_code, 200)
        expected = list(Countries.objects.order_by("country_name").values_list("country_name", flat=True))
        self.assertEqual(response.json()["countries"], expected)
        self.assertIn("Australia", expected)


class RegistrationUniversitiesTests(TestCase):
    def test_lists_management_known_universities_in_order_to_anyone(self):
        from apps.users.models import KnownUniversity

        for name in ("UNSW Sydney", "The University of Sydney", "Monash University"):
            KnownUniversity.objects.create(name=name)

        response = APIClient().get("/api/v1/registration/universities/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["universities"],
            ["Monash University", "The University of Sydney", "UNSW Sydney"],
        )
