"""The Finalist Presentation tab: this year's times, on the Symposium date
set on Notify Finalists, which admins add, change and remove; and each
finalist student's answer, the times they can make; and the slides each
finalist team hands in."""
from datetime import date, time

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.grading.models import (
    FinalistEmailSettings,
    FinalistFlag,
    FinalistSlides,
    PresentationAvailability,
    PresentationSlot,
)
from apps.groups.models import GroupMembership, Groups
from apps.submissions.services import current_cohort
from apps.users.models import User

from .fixtures import _GradingFixture

LIST = "grading:presentation-slots"


class PresentationSlotTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        self.year = current_cohort()

    def _add(self, starts_at, ends_at):
        return self.client.post(reverse(LIST), {"starts_at": starts_at, "ends_at": ends_at}, format="json")

    def _detail(self, slot_id):
        return reverse("grading:presentation-slot-detail", args=[slot_id])

    def test_times_are_added_and_listed_earliest_first(self):
        self.assertEqual(self._add("11:00", "11:30").status_code, status.HTTP_201_CREATED)
        r = self._add("09:30", "10:00")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        # Each change answers with the whole list.
        self.assertEqual(
            [(s["starts_at"], s["ends_at"]) for s in r.json()["slots"]],
            [("09:30", "10:00"), ("11:00", "11:30")],
        )
        self.assertEqual(r.json()["year"], self.year)
        self.assertTrue(PresentationSlot.objects.filter(year=self.year).count() == 2)

    def test_the_list_carries_the_symposium_date_once_it_is_set(self):
        self.assertIsNone(self.client.get(reverse(LIST)).json()["symposium_date"])
        FinalistEmailSettings.objects.update_or_create(pk=1, defaults={"symposium_date": date(2026, 10, 23)})
        self.assertEqual(self.client.get(reverse(LIST)).json()["symposium_date"], "2026-10-23")

    def test_a_time_must_end_after_it_starts(self):
        r = self._add("10:00", "10:00")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.json()["error"], "The end time must be after the start time.")
        self.assertFalse(PresentationSlot.objects.exists())

    def test_the_same_time_cannot_be_listed_twice(self):
        self._add("10:00", "10:30")
        r = self._add("10:00", "10:30")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.json()["error"], "That time is already listed.")

    def test_a_time_can_be_changed_and_removed(self):
        slot_id = self._add("10:00", "10:30").json()["slots"][0]["id"]
        r = self.client.patch(self._detail(slot_id), {"ends_at": "10:45"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(r.json()["slots"][0]["ends_at"], "10:45")
        # A change is checked like a new one.
        r = self.client.patch(self._detail(slot_id), {"starts_at": "11:00"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

        r = self.client.delete(self._detail(slot_id))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()["slots"], [])

    def test_each_year_has_its_own_times(self):
        old = PresentationSlot.objects.create(year=self.year - 1, starts_at=time(9), ends_at=time(10))
        # Last year's aren't listed, and can't be changed from this year's tab.
        self.assertEqual(self.client.get(reverse(LIST)).json()["slots"], [])
        self.assertEqual(self.client.delete(self._detail(old.id)).status_code, status.HTTP_404_NOT_FOUND)
        # Last year's times don't block the same ones this year.
        self.assertEqual(self._add("09:00", "10:00").status_code, status.HTTP_201_CREATED)

    def test_graders_only(self):
        self.client.force_authenticate(self.non_staff)
        self.assertEqual(self.client.get(reverse(LIST)).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self._add("10:00", "10:30").status_code, status.HTTP_403_FORBIDDEN)


def _member(email, group, role="student"):
    first, last = email.split("@")[0].split(".")
    user = User.objects.create_user(email=email, first_name=first.title(), last_name=last.title(), password="pw12345!")
    GroupMembership.objects.create(user=user, group=group, membership_role=role)
    return user


class PresentationResponseTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        year = current_cohort()
        self.morning = PresentationSlot.objects.create(year=year, starts_at=time(9), ends_at=time(9, 30))
        self.noon = PresentationSlot.objects.create(year=year, starts_at=time(12), ends_at=time(12, 30))
        # Two finalist teams, listed by number; a mentor, and a team that isn't one.
        self.btf10 = Groups.objects.create(group_name="BTF10")
        self.btf2 = Groups.objects.create(group_name="BTF2")
        for team in (self.btf10, self.btf2):
            FinalistFlag.objects.create(group=team, flagged_by=self.staff)
        self.zoe = _member("zoe.lee@example.com", self.btf2)
        self.amy = _member("amy.chen@example.com", self.btf2)
        _member("mo.mentor@example.com", self.btf2, role="mentor")
        _member("ben.wu@example.com", self.btf10)
        _member("not.finalist@example.com", self.group)
        answer = PresentationAvailability.objects.create(group=self.btf2, user=self.zoe)
        answer.slots.set([self.noon, self.morning])

    def _teams(self):
        r = self.client.get(reverse("grading:presentation-responses"))
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        return r.json()["teams"]

    def test_each_finalist_student_and_the_times_they_can_make(self):
        teams = self._teams()
        self.assertEqual([t["group_name"] for t in teams], ["BTF2", "BTF10"])
        btf2 = teams[0]["students"]
        # Students only, by name; one hasn't answered yet.
        self.assertEqual([s["name"] for s in btf2], ["Amy Chen", "Zoe Lee"])
        self.assertEqual((btf2[0]["responded"], btf2[0]["slot_ids"]), (False, []))
        self.assertEqual((btf2[1]["responded"], btf2[1]["slot_ids"]), (True, sorted([self.morning.id, self.noon.id])))
        self.assertIsNotNone(btf2[1]["updated_at"])

    def _allocate(self, team, slot_id):
        return self.client.put(
            reverse("grading:presentation-allocation", args=[team.id]), {"slot_id": slot_id}, format="json"
        )

    def test_a_team_is_given_a_time_and_it_can_be_taken_away(self):
        r = self._allocate(self.btf2, self.noon.id)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(r.json(), {"group_id": self.btf2.id, "slot_id": self.noon.id})
        teams = {t["group_name"]: t for t in self._teams()}
        self.assertEqual(teams["BTF2"]["allocated_slot_id"], self.noon.id)
        self.assertIsNone(teams["BTF10"]["allocated_slot_id"])
        # Several teams may share a time.
        self.assertEqual(self._allocate(self.btf10, self.noon.id).status_code, status.HTTP_200_OK)

        self._allocate(self.btf2, None)
        self.assertIsNone(self._teams()[0]["allocated_slot_id"])

    def test_only_this_years_times_and_finalist_teams(self):
        old = PresentationSlot.objects.create(year=current_cohort() - 1, starts_at=time(9), ends_at=time(10))
        for bad in (old.id, 99999, True, "x"):
            with self.subTest(slot_id=bad):
                r = self._allocate(self.btf2, bad)
                self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(r.json()["detail"], "That time isn't one of this year's.")
        # The fixture's team isn't a finalist.
        self.assertEqual(self._allocate(self.group, self.noon.id).status_code, status.HTTP_404_NOT_FOUND)

    def test_removing_a_time_clears_it_from_the_teams_given_it(self):
        self._allocate(self.btf2, self.noon.id)
        self.client.delete(reverse("grading:presentation-slot-detail", args=[self.noon.id]))
        self.assertIsNone(self._teams()[0]["allocated_slot_id"])

    def test_a_removed_time_drops_out_of_the_answers(self):
        self.client.delete(reverse("grading:presentation-slot-detail", args=[self.noon.id]))
        zoe = self._teams()[0]["students"][1]
        self.assertEqual(zoe["slot_ids"], [self.morning.id])

    def test_graders_only(self):
        self.client.force_authenticate(self.non_staff)
        self.assertEqual(
            self.client.get(reverse("grading:presentation-responses")).status_code, status.HTTP_403_FORBIDDEN
        )
        self.assertEqual(self._allocate(self.btf2, self.noon.id).status_code, status.HTTP_403_FORBIDDEN)


class FinalistSlidesTests(_GradingFixture):
    def setUp(self):
        from django.utils import timezone

        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        self.btf10 = Groups.objects.create(group_name="BTF10")
        self.btf2 = Groups.objects.create(group_name="BTF2")
        for team in (self.btf10, self.btf2):
            FinalistFlag.objects.create(group=team, flagged_by=self.staff)
        self.amy = _member("amy.chen@example.com", self.btf10)
        self.handed_in = timezone.now()
        FinalistSlides.objects.create(
            group=self.btf10,
            file={"storage_key": "slides/btf10.pptx", "name": "BTF10 slides.pptx", "mime": "x", "size": 1},
            submitted_by=self.amy,
            submitted_at=self.handed_in,
        )

    def _get(self):
        r = self.client.get(reverse("grading:presentation-slides"))
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        return r.json()

    def test_each_finalist_team_and_its_slides(self):
        body = self._get()
        # Finalist teams only, slides handed in first; the one without says so.
        self.assertEqual([t["group_name"] for t in body["teams"]], ["BTF10", "BTF2"])
        btf10, btf2 = body["teams"]
        self.assertEqual(
            (btf2["submitted"], btf2["file_name"], btf2["submitted_by"], btf2["submitted_at"]),
            (False, "", None, None),
        )
        self.assertEqual((btf10["submitted"], btf10["file_name"], btf10["submitted_by"]), (True, "BTF10 slides.pptx", "Amy Chen"))
        self.assertIsNotNone(btf10["submitted_at"])

    def test_the_latest_handed_in_come_first(self):
        from datetime import timedelta

        btf5 = Groups.objects.create(group_name="BTF5")
        btf7 = Groups.objects.create(group_name="BTF7")
        for team in (btf5, btf7):
            FinalistFlag.objects.create(group=team, flagged_by=self.staff)
        # BTF7 an hour after BTF10, BTF5 an hour before; BTF2 not yet.
        for team, hours in ((btf7, 1), (btf5, -1)):
            FinalistSlides.objects.create(
                group=team, file={"name": "s.pdf"}, submitted_at=self.handed_in + timedelta(hours=hours),
            )
        self.assertEqual(
            [t["group_name"] for t in self._get()["teams"]], ["BTF7", "BTF10", "BTF5", "BTF2"]
        )

    def test_it_carries_the_slides_due_date_once_it_is_set(self):
        self.assertIsNone(self._get()["slides_due"])
        FinalistEmailSettings.objects.update_or_create(pk=1, defaults={"slides_due": date(2026, 10, 16)})
        self.assertEqual(self._get()["slides_due"], "2026-10-16")

    def test_graders_only(self):
        self.client.force_authenticate(self.non_staff)
        self.assertEqual(
            self.client.get(reverse("grading:presentation-slides")).status_code, status.HTTP_403_FORBIDDEN
        )


@override_settings(USE_AZURE_BLOB_STORAGE=False)
class FinalistSlidesOpenTests(_GradingFixture):
    def setUp(self):
        import tempfile

        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.utils import timezone

        from apps.common.storage import reset_managed_storage_caches
        from apps.grading.views.presentation import SLIDES_FILES

        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        media_setting = override_settings(MEDIA_ROOT=media.name)
        media_setting.enable()
        self.addCleanup(media_setting.disable)
        reset_managed_storage_caches()
        self.addCleanup(reset_managed_storage_caches)

        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        self.team = Groups.objects.create(group_name="BTF3")
        FinalistFlag.objects.create(group=self.team, flagged_by=self.staff)
        self.deck = FinalistSlides.objects.create(
            group=self.team,
            file=SLIDES_FILES.save_uploaded_file(
                SimpleUploadedFile("BTF3 slides.pdf", b"%PDF-1.4 slides", content_type="application/pdf"),
                content_type_field="mime",
                size_field="size",
                original_filename_field="name",
            ),
            submitted_at=timezone.now(),
        )

    def _open(self, group_id):
        response = self.client.get(reverse("grading:presentation-slides-file", args=[group_id]))
        # Lets go of the file, so the temporary folder can be removed.
        self.addCleanup(response.close)
        return response

    def test_a_teams_pdf_opens_in_the_browser(self):
        r = self._open(self.team.id)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(r.streaming_content), b"%PDF-1.4 slides")
        self.assertTrue(r["Content-Disposition"].startswith("inline"))

    def test_other_files_download(self):
        self.deck.file = {**self.deck.file, "mime": "application/vnd.ms-powerpoint"}
        self.deck.save()
        self.assertTrue(self._open(self.team.id)["Content-Disposition"].startswith("attachment"))

    def test_nothing_to_open_until_slides_are_in(self):
        other = Groups.objects.create(group_name="BTF4")
        FinalistFlag.objects.create(group=other, flagged_by=self.staff)
        self.assertEqual(self._open(other.id).status_code, status.HTTP_404_NOT_FOUND)
        # Nor for a team that isn't a finalist.
        self.assertEqual(self._open(self.group.id).status_code, status.HTTP_404_NOT_FOUND)

    def test_graders_only(self):
        self.client.force_authenticate(self.non_staff)
        self.assertEqual(self._open(self.team.id).status_code, status.HTTP_403_FORBIDDEN)
