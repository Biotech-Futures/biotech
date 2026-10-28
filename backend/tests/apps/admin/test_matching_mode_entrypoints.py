"""Component tests: both algorithms normalise an unknown ``mode`` on entry.

``apps.common.matching_modes.resolve_match_mode`` is the unit contract; these
tests check the layer above it - that ``match_mentors`` and the student entry
points (``build_groups`` / ``recommend_groups_by_country``) actually call it,
so an unrecognised mode runs ``balanced`` rather than whatever path happens to
follow an unmatched ``if``.

That matters because the mentor matcher's branches are ``balanced``, then
``strict``, then an unguarded coverage fall-through: before normalisation
happened on entry, ``match_mentors(..., mode="nonsense")`` silently ran
coverage. The assertions below are stronger than "does not raise" - every
fixture is chosen so all three modes *disagree*, which is what makes
"unknown == balanced" meaningful. The explicit-mode test in each class guards
the fixture itself: if it stops diverging, that test fails first and points at
the data rather than at the normalisation.
"""

from django.test import SimpleTestCase

from apps.admin.algorithms.mentor import match_mentors
from apps.admin.algorithms.student import (
    build_groups,
    format_recommendation_input,
    recommend_groups_by_country,
)


def student(student_id, country, timezone_offset, year_level=10, interests=("Genomics",)):
    return {
        "id": student_id,
        "country": country,
        "timezoneOffsetHours": timezone_offset,
        "yearLevel": year_level,
        "interests": list(interests),
    }


def existing_group(group_id, name, members):
    return {
        "id": group_id,
        "groupName": name,
        "groupStudent": list(members),
        "tutor": {"id": 99, "name": ""},
    }


def recommendation_input(groups, students):
    return format_recommendation_input(
        [
            {
                "userId": member["id"],
                "firstName": f"Existing{member['id']}",
                "lastName": "",
                "countryName": member["country"],
                "timezoneOffsetHours": member["timezoneOffsetHours"],
                "yearLevel": member["yearLevel"],
                "interests": member["interests"],
                "groupId": group["id"],
                "groupName": group["groupName"],
                "groupTutorId": 99,
                "groupTutorName": "",
            }
            for group in groups
            for member in group["groupStudent"]
        ],
        [
            {
                "userId": candidate["id"],
                "firstName": f"Join{candidate['id']}",
                "lastName": "",
                "countryName": candidate["country"],
                "timezoneOffsetHours": candidate["timezoneOffsetHours"],
                "yearLevel": candidate["yearLevel"],
                "interests": candidate["interests"],
            }
            for candidate in students
        ],
    )


class MentorAlgorithmModeTests(SimpleTestCase):
    """``match_mentors`` must normalise ``mode`` before branching."""

    def setUp(self):
        # One Australian group. Mentor 1 shares its country but none of its
        # interests (so balanced skips it); mentor 2 shares its interests but
        # not its country (so strict and coverage's same-country phase skip
        # it). Every mode therefore picks a different mentor.
        self.groups = [
            {
                "groupId": 10,
                "groupName": "NSW Bio",
                "countryName": "Australia",
                "utcOffsetHours": 10.0,
                "studentInterests": ["Genomics"],
                "studentCount": 3,
            }
        ]
        self.mentors = [
            {
                "mentorId": 1,
                "firstName": "Ana",
                "lastName": "Aussie",
                "countryName": "Australia",
                "utcOffsetHours": 10.0,
                "institution": None,
                "interests": ["History"],
                "maxGroupCount": 1,
                "currentAcceptedCount": 0,
            },
            {
                "mentorId": 2,
                "firstName": "Ben",
                "lastName": "Bengal",
                "countryName": "India",
                "utcOffsetHours": 5.5,
                "institution": None,
                "interests": ["Genomics"],
                "maxGroupCount": 1,
                "currentAcceptedCount": 0,
            },
        ]

    @staticmethod
    def _recommended_mentor_ids(results):
        return [
            result["recommendedMentor"]["mentorId"]
            if result["recommendedMentor"]
            else None
            for result in results
        ]

    def test_fixture_diverges_across_the_three_modes(self):
        balanced = match_mentors(self.groups, self.mentors, "balanced")
        strict = match_mentors(self.groups, self.mentors, "strict")
        coverage = match_mentors(self.groups, self.mentors, "coverage")

        self.assertEqual(self._recommended_mentor_ids(balanced), [2])
        self.assertEqual(self._recommended_mentor_ids(strict), [1])
        self.assertEqual(self._recommended_mentor_ids(coverage), [1])
        self.assertNotEqual(balanced, coverage)

    def test_unknown_mode_runs_balanced_not_the_coverage_fall_through(self):
        unknown = match_mentors(self.groups, self.mentors, "not-a-real-mode")
        balanced = match_mentors(self.groups, self.mentors, "balanced")
        coverage = match_mentors(self.groups, self.mentors, "coverage")

        self.assertEqual(unknown, balanced)
        self.assertNotEqual(unknown, coverage)

    def test_unknown_mode_is_not_strict_either(self):
        unknown = match_mentors(self.groups, self.mentors, "bogus")
        strict = match_mentors(self.groups, self.mentors, "strict")

        self.assertNotEqual(unknown, strict)

    def test_default_argument_matches_explicit_balanced(self):
        self.assertEqual(
            match_mentors(self.groups, self.mentors),
            match_mentors(self.groups, self.mentors, "balanced"),
        )


class StudentAlgorithmModeTests(SimpleTestCase):
    """``build_groups`` and ``recommend_groups_by_country`` normalise too."""

    @staticmethod
    def _placed(result):
        return {
            student_id
            for group in result["groups"]
            for student_id in group["studentIds"]
        }

    @staticmethod
    def _coverage_pool():
        # A1-A4 fit in one group but A3 is a year away from the others, so
        # balanced scoring strands A3 while coverage accepts the weaker group.
        return [
            student("A1", "Australia", 10),
            student("A2", "Australia", 10),
            student("A3", "Australia", 10, year_level=12),
            student("A4", "Australia", 10),
            student("B1", "Brazil", -3),
            student("B2", "Brazil", -3),
        ]

    @staticmethod
    def _strict_pool():
        # Two Australians plus two singletons: balanced reaches across
        # borders to place anyone, strict must refuse to.
        return [
            student("s1", "Australia", 10),
            student("s2", "Australia", 10),
            student("s3", "Brazil", -3),
            student("s4", "Canada", -5),
        ]

    def test_build_groups_fixture_diverges_across_the_three_modes(self):
        balanced = build_groups(self._strict_pool(), mode="balanced")
        strict = build_groups(self._strict_pool(), mode="strict")

        self.assertEqual(self._placed(balanced), {"s1", "s2", "s3", "s4"})
        self.assertEqual(self._placed(strict), {"s1", "s2"})
        self.assertEqual(strict["unmatchedStudentIds"], ["s3", "s4"])

        coverage_pool = self._coverage_pool()
        self.assertEqual(
            build_groups(coverage_pool, mode="balanced")["unmatchedStudentIds"],
            ["A3"],
        )
        self.assertEqual(
            build_groups(coverage_pool, mode="coverage")["unmatchedStudentIds"],
            [],
        )

    def test_unknown_mode_forms_the_balanced_groups_not_strict(self):
        unknown = build_groups(self._strict_pool(), mode="not-a-real-mode")
        balanced = build_groups(self._strict_pool(), mode="balanced")
        strict = build_groups(self._strict_pool(), mode="strict")

        self.assertEqual(unknown, balanced)
        self.assertNotEqual(unknown, strict)

    def test_unknown_mode_does_not_take_the_coverage_path(self):
        unknown = build_groups(self._coverage_pool(), mode="bogus")
        balanced = build_groups(self._coverage_pool(), mode="balanced")
        coverage = build_groups(self._coverage_pool(), mode="coverage")

        self.assertEqual(unknown, balanced)
        self.assertNotEqual(unknown, coverage)

    def test_default_argument_matches_explicit_balanced(self):
        self.assertEqual(
            build_groups(self._strict_pool()),
            build_groups(self._strict_pool(), mode="balanced"),
        )

    @staticmethod
    def _recommendations(mode):
        nsw = existing_group(20, "NSW Bio", [student(1, "Australia", 10)])
        sp = existing_group(21, "SP Bio", [student(2, "Brazil", -3)])
        return recommend_groups_by_country(
            recommendation_input(
                [nsw, sp],
                [
                    student(3, "Australia", 10),
                    student(4, "Brazil", -3),
                    student(5, "Canada", -5),
                ],
            ),
            mode=mode,
        )

    @staticmethod
    def _group_ids_by_student(recommendations):
        return {
            recommendation["student"]["id"]: (
                recommendation["recommendGroup"]["id"]
                if recommendation["recommendGroup"]
                else None
            )
            for recommendation in recommendations
        }

    def test_recommend_fixture_diverges_across_the_three_modes(self):
        strict = self._group_ids_by_student(self._recommendations("strict"))
        balanced = self._group_ids_by_student(self._recommendations("balanced"))

        # Strict only recommends same-country groups; balanced still reaches
        # across the border for the Canadian.
        self.assertEqual(strict[5], None)
        self.assertIsNotNone(balanced[5])
        self.assertNotEqual(strict, balanced)

    def test_unknown_mode_ranks_recommendations_like_balanced(self):
        unknown = self._recommendations("not-a-real-mode")

        self.assertEqual(unknown, self._recommendations("balanced"))
        self.assertNotEqual(unknown, self._recommendations("strict"))

    def test_default_recommendations_match_explicit_balanced(self):
        nsw = existing_group(20, "NSW Bio", [student(1, "Australia", 10)])

        self.assertEqual(
            recommend_groups_by_country(recommendation_input([nsw], [student(3, "Canada", -5)])),
            recommend_groups_by_country(
                recommendation_input([nsw], [student(3, "Canada", -5)]),
                mode="balanced",
            ),
        )
