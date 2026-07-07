from django.test import SimpleTestCase

from apps.admin.algorithms.student import (
    build_groups,
    format_recommendation_input,
    recommend_groups_by_country,
    round2,
)


class StudentAlgorithmParityTests(SimpleTestCase):
    """Parity checks for the geography-keyed student matching algorithm.

    The algorithm partitions and scores by country (derived from the user's
    state), so fixtures use ``country`` rather than the removed track concept.
    """

    def test_round2_matches_typescript_math_round(self):
        self.assertEqual(round2(1.005), 1.0)
        self.assertEqual(round2(1.015), 1.01)
        self.assertEqual(round2(1.025), 1.02)

    def test_build_groups_matches_typescript_ordering_and_scores(self):
        result = build_groups([
            {
                "id": "s10",
                "country": "Australia",
                "timezoneOffsetHours": 10,
                "yearLevel": 10,
                "interests": ["Genomics"],
            },
            {
                "id": "s2",
                "country": "Australia",
                "timezoneOffsetHours": 10,
                "yearLevel": 11,
                "interests": ["Genomics"],
            },
        ])

        self.assertEqual(result["groups"], [
            {
                "country": "Australia",
                "studentIds": ["s10", "s2"],
                "groupSize": 2,
                "groupScore": 92.0,
                "scoreBreakdown": {
                    "baseScore": 100,
                    "yearPenalty": 8.0,
                    "countryPenalty": 0.0,
                    "timezonePenalty": 0.0,
                    "totalPenalty": 8.0,
                    "sizeBonus": 0,
                    "objectiveScore": 92.0,
                },
            }
        ])
        self.assertEqual(
            result["studentScores"][0]["groupStudentIds"], ["s10", "s2"]
        )

    def test_existing_group_recommendations_match_typescript_shape(self):
        input_by_country = format_recommendation_input(
            [
                {
                    "userId": 1,
                    "firstName": "Existing",
                    "lastName": "One",
                    "countryName": "Australia",
                    "timezoneOffsetHours": 10,
                    "yearLevel": 10,
                    "interests": ["Genomics"],
                    "groupId": 20,
                    "groupName": "NSW Bio",
                    "groupTutorId": 99,
                    "groupTutorName": "",
                }
            ],
            [
                {
                    "userId": 3,
                    "firstName": "Join",
                    "lastName": "NSW",
                    "countryName": "Australia",
                    "timezoneOffsetHours": 10,
                    "yearLevel": 10,
                    "interests": ["Genomics", "Other"],
                }
            ],
        )

        recommendations = recommend_groups_by_country(input_by_country)

        self.assertEqual(recommendations, [
            {
                "student": {
                    "id": 3,
                    "name": "Join NSW",
                    "country": "Australia",
                    "timezoneOffsetHours": 10,
                    "yearLevel": 10,
                    "interests": ["Genomics", "Other"],
                },
                "recommendGroup": {
                    "id": 20,
                    "groupName": "NSW Bio",
                    "groupStudent": [
                        {
                            "id": 1,
                            "name": "Existing One",
                            "country": "Australia",
                            "timezoneOffsetHours": 10,
                            "yearLevel": 10,
                            "interests": ["Genomics"],
                        }
                    ],
                    "tutor": {"id": 99, "name": ""},
                },
                "reason": "Shares interest 'genomics' with the group and matches the same country.",
                "score": 100.0,
                "scoreBreakdown": {
                    "baseScore": 100,
                    "yearPenalty": 0.0,
                    "countryPenalty": 0.0,
                    "timezonePenalty": 0.0,
                    "sizeBonus": 0,
                    "totalPenalty": 0.0,
                    "objectiveScore": 100.0,
                },
            }
        ])
