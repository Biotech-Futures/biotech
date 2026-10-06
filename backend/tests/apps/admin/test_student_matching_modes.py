"""Tests for MA2 (balanced/strict/coverage) and MA4 (country as a tie-break)."""

from django.test import SimpleTestCase

from apps.admin.algorithms.student import (
    build_groups,
    compare_recommendation_candidate,
    format_recommendation_input,
    recommend_groups_by_country,
    score_student_for_existing_group,
)
from apps.common.matching_weights import ScoringWeights


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


class StudentMatchingModeTests(SimpleTestCase):
    def setUp(self):
        # Two Australians plus two singletons: balanced has to reach across
        # borders to place anyone, strict must refuse to.
        self.pool = [
            student("s1", "Australia", 10),
            student("s2", "Australia", 10),
            student("s3", "Brazil", -3),
            student("s4", "Canada", -5),
        ]

    @staticmethod
    def _placed_ids(result):
        return {
            student_id
            for group in result["groups"]
            for student_id in group["studentIds"]
        }

    def test_balanced_groups_across_countries_when_needed(self):
        result = build_groups(self.pool, mode="balanced")

        self.assertEqual(self._placed_ids(result), {"s1", "s2", "s3", "s4"})
        self.assertEqual(result["unmatchedStudentIds"], [])

    def test_strict_never_groups_across_countries(self):
        result = build_groups(self.pool, mode="strict")

        self.assertEqual(
            [group["studentIds"] for group in result["groups"]], [["s1", "s2"]]
        )
        self.assertEqual(result["unmatchedStudentIds"], ["s3", "s4"])

    def test_coverage_places_the_student_balanced_would_strand(self):
        # A1-A4 fit in one group but A3 is a year away from the others, so
        # balanced scoring strands A3 and forms a clean group without them.
        pool = [
            student("A1", "Australia", 10),
            student("A2", "Australia", 10),
            student("A3", "Australia", 10, year_level=12),
            student("A4", "Australia", 10),
            student("B1", "Brazil", -3),
            student("B2", "Brazil", -3),
        ]

        balanced = build_groups(pool, mode="balanced")
        coverage = build_groups(pool, mode="coverage")

        self.assertEqual(balanced["unmatchedStudentIds"], ["A3"])
        self.assertEqual(coverage["unmatchedStudentIds"], [])
        self.assertEqual(self._placed_ids(coverage), {"A1", "A2", "A3", "A4", "B1", "B2"})
        # Coverage accepts the weaker group rather than stranding A3.
        self.assertEqual(
            sorted(len(group["studentIds"]) for group in coverage["groups"]), [2, 4]
        )

    def test_strict_recommends_only_same_country_groups(self):
        nsw = existing_group(20, "NSW Bio", [student(1, "Australia", 10)])
        sp = existing_group(21, "SP Bio", [student(2, "Brazil", -3)])

        recommendations = recommend_groups_by_country(
            recommendation_input(
                [nsw, sp],
                [
                    student(3, "Australia", 10),
                    student(4, "Brazil", -3),
                    student(5, "Canada", -5),
                ],
            ),
            mode="strict",
        )

        matched = {
            recommendation["student"]["id"]: recommendation["recommendGroup"]["id"]
            for recommendation in recommendations
            if recommendation["recommendGroup"]
        }
        self.assertEqual(matched, {3: 20, 4: 21})
        self.assertEqual(
            [
                recommendation["student"]["id"]
                for recommendation in recommendations
                if not recommendation["recommendGroup"]
            ],
            [5],
        )

    def test_balanced_recommends_a_cross_country_group(self):
        nsw = existing_group(20, "NSW Bio", [student(1, "Australia", 10)])

        recommendations = recommend_groups_by_country(
            recommendation_input([nsw], [student(3, "Canada", -5)]),
            mode="balanced",
        )

        self.assertEqual(recommendations[0]["recommendGroup"]["id"], 20)


class CountryTieBreakTests(SimpleTestCase):
    def test_country_is_reported_but_never_penalised(self):
        candidate = score_student_for_existing_group(
            student(3, "Canada", -5),
            existing_group(20, "NSW Bio", [student(1, "Australia", 10)]),
        )

        breakdown = candidate["scoreBreakdown"]
        # Reported for transparency...
        self.assertEqual(breakdown["countryPenalty"], 12.0)
        # ...but the blended penalty ignores it.
        self.assertEqual(
            breakdown["totalPenalty"],
            breakdown["yearPenalty"] + breakdown["timezonePenalty"],
        )
        self.assertEqual(breakdown["timezonePenalty"], 18.0)
        self.assertEqual(candidate["countryMismatchCount"], 1)

    def test_same_timezone_gap_prefers_same_country(self):
        # Identical year gaps and zero timezone gaps on both sides, so country is
        # the only thing left to separate them.
        same_country = score_student_for_existing_group(
            student(3, "Australia", 10),
            existing_group(20, "NSW Bio", [student(1, "Australia", 10)]),
        )
        cross_country = score_student_for_existing_group(
            student(3, "Brazil", 0),
            existing_group(21, "SP Bio", [student(2, "Australia", 0)]),
        )

        self.assertEqual(same_country["averageTimezoneGap"], cross_country["averageTimezoneGap"])
        self.assertEqual(
            same_country["scoreBreakdown"]["objectiveScore"],
            cross_country["scoreBreakdown"]["objectiveScore"],
        )
        self.assertLess(compare_recommendation_candidate(same_country, cross_country), 0)
        self.assertGreater(compare_recommendation_candidate(cross_country, same_country), 0)

    def test_country_tie_break_survives_a_zero_country_weight(self):
        # An admin may set country_mismatch_weight to 0 because country no
        # longer scores; the tie-break must not disappear along with it.
        weights = ScoringWeights(
            year_weight=20.0,
            country_mismatch_penalty=0.0,
            timezone_weight=25.0,
            timezone_max_penalty=20.0,
            size_bonus_weight=20.0,
        )
        same_country = score_student_for_existing_group(
            student(3, "Australia", 10),
            existing_group(20, "NSW Bio", [student(1, "Australia", 10)]),
            weights=weights,
        )
        cross_country = score_student_for_existing_group(
            student(3, "Brazil", 0),
            existing_group(21, "SP Bio", [student(2, "Australia", 0)]),
            weights=weights,
        )

        self.assertEqual(same_country["scoreBreakdown"]["countryPenalty"], 0.0)
        self.assertEqual(cross_country["scoreBreakdown"]["countryPenalty"], 0.0)
        self.assertLess(compare_recommendation_candidate(same_country, cross_country), 0)

    def test_closer_timezone_ranks_first_across_borders(self):
        nearby = score_student_for_existing_group(
            student(3, "Canada", -5),
            existing_group(21, "ON Bio", [student(2, "Australia", -4)]),
        )
        further = score_student_for_existing_group(
            student(3, "Canada", -5),
            existing_group(20, "NSW Bio", [student(1, "Australia", -11)]),
        )

        self.assertLess(nearby["averageTimezoneGap"], further["averageTimezoneGap"])
        self.assertGreater(nearby["score"], further["score"])
        self.assertLess(compare_recommendation_candidate(nearby, further), 0)


class ConfigurableScoringTests(SimpleTestCase):
    def test_configured_weights_replace_the_hardcoded_penalties(self):
        heavy_year = ScoringWeights(
            year_weight=40.0,
            country_mismatch_penalty=10.0,
            timezone_weight=20.0,
            timezone_max_penalty=15.0,
            size_bonus_weight=15.0,
        )
        members = [
            student(1, "Australia", 10, year_level=10),
            student(2, "Australia", 10, year_level=12),
        ]

        result = build_groups(members, weights=heavy_year)

        breakdown = result["groups"][0]["scoreBreakdown"]
        # Two years apart at 40 points per year, against the same 100-point base.
        self.assertEqual(breakdown["yearPenalty"], 80.0)
        self.assertEqual(breakdown["totalPenalty"], 80.0)
        self.assertEqual(result["groups"][0]["groupScore"], 20.0)

    def test_default_weights_keep_the_previous_scores(self):
        members = [
            student(1, "Australia", 10, year_level=10),
            student(2, "Australia", 10, year_level=12),
        ]

        result = build_groups(members)

        self.assertEqual(result["groups"][0]["groupScore"], 84.0)

    def test_size_bonus_weight_scales_the_objective_ceiling(self):
        generous = ScoringWeights(
            year_weight=20.0,
            country_mismatch_penalty=15.0,
            timezone_weight=25.0,
            timezone_max_penalty=20.0,
            size_bonus_weight=20.0,
        )
        members = [student(index, "Australia", 10) for index in range(1, 6)]

        result = build_groups(members, weights=generous)

        breakdown = result["groups"][0]["scoreBreakdown"]
        # A full group earns the whole size_bonus_weight, so the ceiling moves
        # with the configured weight instead of a hardcoded 106.
        self.assertEqual(breakdown["sizeBonus"], 20.0)
        self.assertEqual(breakdown["objectiveScore"], 120.0)