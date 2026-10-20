"""/api/v1/admin/known-university/: the list of names the registration school
check treats as universities (apps.admin.services.known_university)."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from rest_framework import status
from rest_framework.test import APITestCase

from apps.audit.models import AuditLog
from apps.users.models import AdminScope, KnownUniversity
from apps.users.serializers import UserRegisterBodySerializer

User = get_user_model()

LIST_URL = "/api/v1/admin/known-university/"


def detail_url(university_id):
    return f"{LIST_URL}{university_id}/"


class KnownUniversityApiTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email="uni.admin@example.com")
        AdminScope.objects.create(user=self.admin)
        self.client.force_authenticate(self.admin)

    def add(self, name):
        return self.client.post(LIST_URL, {"name": name}, format="json")

    def names(self):
        return list(KnownUniversity.objects.values_list("name", flat=True))

    def assertRefused(self, response, code, msg_part):
        self.assertEqual(response.status_code, code, response.content)
        body = response.json()
        self.assertIsNone(body["data"])
        self.assertIn(msg_part, body["msg"])


class PermissionTests(KnownUniversityApiTestCase):
    def test_anonymous_and_non_admin_users_are_refused_on_every_method(self):
        listed = KnownUniversity.objects.create(name="USYD")
        callers = {
            "anonymous": None,
            "student": User.objects.create_user(email="student@example.com"),
            "staff": User.objects.create_user(email="staff@example.com", is_staff=True),
        }
        for who, user in callers.items():
            self.client.force_authenticate(user)
            for method, url, data in (
                ("get", LIST_URL, None),
                ("post", LIST_URL, {"name": "UNSW"}),
                ("patch", detail_url(listed.pk), {"name": "UNSW"}),
                ("delete", detail_url(listed.pk), None),
            ):
                with self.subTest(who=who, method=method):
                    response = getattr(self.client, method)(url, data, format="json")
                    self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.assertEqual(self.names(), ["USYD"])


class ListTests(KnownUniversityApiTestCase):
    def test_lists_every_name_alphabetically(self):
        KnownUniversity.objects.create(name="UNSW")
        usyd = KnownUniversity.objects.create(name="USYD")
        KnownUniversity.objects.create(name="Monash University")

        response = self.client.get(LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["msg"], "Known universities retrieved successfully")
        self.assertEqual(body["data"]["total"], 3)
        self.assertEqual([item["name"] for item in body["data"]["items"]], ["Monash University", "UNSW", "USYD"])
        self.assertEqual(
            body["data"]["items"][2],
            {"id": usyd.pk, "name": "USYD", "createdAt": usyd.created_at.isoformat()},
        )

    def test_an_empty_list(self):
        self.assertEqual(self.client.get(LIST_URL).json()["data"], {"items": [], "total": 0})

    def test_search_matches_part_of_a_name_in_any_casing(self):
        KnownUniversity.objects.create(name="University of Sydney")
        KnownUniversity.objects.create(name="Sydney Uni")
        KnownUniversity.objects.create(name="UNSW")

        data = self.client.get(LIST_URL, {"search": " sydney "}).json()["data"]

        self.assertEqual([item["name"] for item in data["items"]], ["Sydney Uni", "University of Sydney"])
        self.assertEqual(data["total"], 2)

    def test_a_blank_search_lists_everything(self):
        KnownUniversity.objects.create(name="UNSW")

        self.assertEqual(self.client.get(LIST_URL, {"search": "  "}).json()["data"]["total"], 1)


class AddTests(KnownUniversityApiTestCase):
    def test_adds_a_name_with_its_spacing_tidied(self):
        response = self.add("  Monash   Uni ")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        body = response.json()
        self.assertEqual(body["msg"], "Known university added successfully")
        university = KnownUniversity.objects.get()
        self.assertEqual(body["data"], {
            "id": university.pk, "name": "Monash Uni", "createdAt": university.created_at.isoformat(),
        })

    def test_the_add_is_recorded_in_the_audit_log(self):
        university_id = self.add("USYD").json()["data"]["id"]

        log = AuditLog.objects.get(entity_type="known_university", action="create")
        self.assertEqual((log.actor_user, log.entity_id, log.after_state), (self.admin, university_id, {"name": "USYD"}))

    def test_a_name_already_listed_in_any_casing_or_spacing_is_refused(self):
        KnownUniversity.objects.create(name="Monash Uni")

        for name in ("Monash Uni", "monash uni", "  MONASH   UNI  "):
            with self.subTest(name=name):
                self.assertRefused(self.add(name), status.HTTP_400_BAD_REQUEST, "already on the list")

        self.assertEqual(self.names(), ["Monash Uni"])
        self.assertFalse(AuditLog.objects.filter(entity_type="known_university").exists())

    def test_a_blank_or_missing_name_is_refused(self):
        for name in ("", "   ", None):
            with self.subTest(name=name):
                self.assertRefused(self.add(name), status.HTTP_400_BAD_REQUEST, "name is required")
        self.assertRefused(self.client.post(LIST_URL, {}, format="json"), 400, "name is required")

        self.assertEqual(self.names(), [])

    def test_a_name_that_isnt_text_is_refused(self):
        for body in ({"name": 42}, {"name": ["USYD"]}, ["USYD"]):
            with self.subTest(body=body):
                self.assertRefused(self.client.post(LIST_URL, body, format="json"), 400, "name is required")

        self.assertEqual(self.names(), [])

    def test_a_name_over_255_characters_is_refused(self):
        self.assertRefused(self.add("U" * 256), status.HTTP_400_BAD_REQUEST, "255 characters or fewer")
        self.assertEqual(self.add("U" * 255).status_code, status.HTTP_201_CREATED)

        self.assertEqual(self.names(), ["U" * 255])

    def test_spacing_is_tidied_before_the_length_is_checked(self):
        self.assertEqual(self.add("   " + "U" * 255 + "   ").status_code, status.HTTP_201_CREATED)

    def test_a_name_added_by_someone_else_at_the_same_moment_is_refused_not_an_error(self):
        # The duplicate check has passed, then the database refuses the second copy.
        with mock.patch.object(KnownUniversity.objects, "create", side_effect=IntegrityError("unique")):
            response = self.add("USYD")

        self.assertRefused(response, status.HTTP_400_BAD_REQUEST, "already on the list")
        self.assertFalse(AuditLog.objects.filter(entity_type="known_university").exists())


class RenameTests(KnownUniversityApiTestCase):
    def rename(self, university, name):
        return self.client.patch(detail_url(university.pk), {"name": name}, format="json")

    def test_renames_a_name_with_its_spacing_tidied_and_records_it(self):
        university = KnownUniversity.objects.create(name="USYD")

        response = self.rename(university, "  Sydney   Uni ")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.json()["data"]["name"], "Sydney Uni")
        self.assertEqual(self.names(), ["Sydney Uni"])
        log = AuditLog.objects.get(entity_type="known_university", action="update")
        self.assertEqual(
            (log.actor_user, log.entity_id, log.before_state, log.after_state),
            (self.admin, university.pk, {"name": "USYD"}, {"name": "Sydney Uni"}),
        )

    def test_its_own_name_in_another_casing_is_fine(self):
        university = KnownUniversity.objects.create(name="usyd")
        response = self.rename(university, "USYD")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(self.names(), ["USYD"])

    def test_another_listed_name_or_a_bad_one_is_refused(self):
        university = KnownUniversity.objects.create(name="USYD")
        KnownUniversity.objects.create(name="UNSW")

        self.assertRefused(self.rename(university, " unsw "), status.HTTP_400_BAD_REQUEST, "already on the list")
        self.assertRefused(self.rename(university, "   "), status.HTTP_400_BAD_REQUEST, "required")
        self.assertRefused(self.rename(university, 42), status.HTTP_400_BAD_REQUEST, "required")
        self.assertRefused(self.rename(university, "x" * 256), status.HTTP_400_BAD_REQUEST, "255 characters")
        self.assertEqual(self.names(), ["UNSW", "USYD"])
        self.assertFalse(AuditLog.objects.filter(entity_type="known_university", action="update").exists())

    def test_the_same_name_changes_nothing(self):
        university = KnownUniversity.objects.create(name="USYD")
        response = self.rename(university, "USYD")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(AuditLog.objects.filter(entity_type="known_university", action="update").exists())

    def test_a_missing_id_is_not_found(self):
        self.assertRefused(
            self.client.patch(detail_url(999999), {"name": "UNSW"}, format="json"), status.HTTP_404_NOT_FOUND, "not found",
        )


class DeleteTests(KnownUniversityApiTestCase):
    def test_deletes_a_name_and_records_it(self):
        university = KnownUniversity.objects.create(name="USYD")

        response = self.client.delete(detail_url(university.pk))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"msg": "Known university deleted successfully", "data": True})
        self.assertEqual(self.names(), [])
        log = AuditLog.objects.get(entity_type="known_university", action="delete")
        self.assertEqual((log.actor_user, log.entity_id, log.before_state), (self.admin, university.pk, {"name": "USYD"}))

    def test_a_missing_id_is_not_found(self):
        self.assertRefused(self.client.delete(detail_url(999999)), status.HTTP_404_NOT_FOUND, "not found")

    def test_a_deleted_name_can_be_added_again(self):
        university = KnownUniversity.objects.create(name="USYD")
        self.client.delete(detail_url(university.pk))

        self.assertEqual(self.add("usyd").status_code, status.HTTP_201_CREATED)


class SchoolWarningTests(KnownUniversityApiTestCase):
    """A name added here is what the registration school check consults."""

    @staticmethod
    def registration(school):
        return UserRegisterBodySerializer(data={
            "Title": "kid@example.com", "FirstName": "Kid", "Surname": "Student",
            "Country": "Australia", "Region": "NSW",
            "GuardianEmail": "parent@example.com", "GuardianName": "Pat", "GuardianSurname": "Parent",
            "SchoolName": school, "YearLevel": "10", "Areaofinterest": "Biotechnology",
        })

    def assertWarned(self, school, warned):
        serializer = self.registration(school)
        self.assertEqual(serializer.is_valid(), not warned, serializer.errors)
        if warned:
            self.assertIn("looks like a university", str(serializer.errors))

    def test_a_name_added_here_makes_the_school_warning_fire(self):
        self.assertWarned("USYD", False)

        self.add("USYD")

        self.assertWarned("usyd", True)
        self.assertWarned("  USYD ", True)

    def test_deleting_it_stops_the_warning(self):
        university_id = self.add("USYD").json()["data"]["id"]
        self.assertWarned("USYD", True)

        self.client.delete(detail_url(university_id))

        self.assertWarned("USYD", False)
