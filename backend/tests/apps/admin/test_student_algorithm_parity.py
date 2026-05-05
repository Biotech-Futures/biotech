from apps.admin.algorithms.student import (
    build_groups,
    format_recommendation_input,
    recommend_groups_by_track,
    round2,
)


def test_round2_matches_typescript_math_round():
    assert round2(1.005) == 1.0
    assert round2(1.015) == 1.01
    assert round2(1.025) == 1.02


def test_build_groups_matches_typescript_ordering_and_scores():
    result = build_groups([
        {
            "id": "s10",
            "trackId": "AUS-NSW",
            "country": "Australia",
            "timezoneOffsetHours": 10,
            "yearLevel": 10,
            "interests": ["Genomics"],
        },
        {
            "id": "s2",
            "trackId": "AUS-NSW",
            "country": "Australia",
            "timezoneOffsetHours": 10,
            "yearLevel": 11,
            "interests": ["Genomics"],
        },
    ])

    assert result["groups"] == [
        {
            "track": "AUS-NSW",
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
    ]
    assert result["studentScores"][0]["groupStudentIds"] == ["s10", "s2"]


def test_existing_group_recommendations_match_typescript_shape():
    input_by_track = format_recommendation_input(
        [
            {
                "userId": 1,
                "firstName": "Existing",
                "lastName": "One",
                "trackCode": "AUS-NSW",
                "countryName": "Australia",
                "timezoneOffsetHours": 10,
                "yearLevel": 10,
                "interests": ["Genomics"],
                "groupId": 20,
                "groupName": "NSW Bio",
                "groupTrackCode": "AUS-NSW",
                "groupTutorId": 99,
                "groupTutorName": "",
            }
        ],
        [
            {
                "userId": 3,
                "firstName": "Join",
                "lastName": "NSW",
                "trackCode": "AUS-NSW",
                "countryName": "Australia",
                "timezoneOffsetHours": 10,
                "yearLevel": 10,
                "interests": ["Genomics", "Other"],
            }
        ],
    )

    recommendations = recommend_groups_by_track(input_by_track)

    assert recommendations == [
        {
            "student": {
                "id": 3,
                "name": "Join NSW",
                "trackId": "AUS-NSW",
                "country": "Australia",
                "timezoneOffsetHours": 10,
                "yearLevel": 10,
                "interests": ["Genomics", "Other"],
            },
            "recommendGroup": {
                "id": 20,
                "groupName": "NSW Bio",
                "trackId": "AUS-NSW",
                "groupStudent": [
                    {
                        "id": 1,
                        "name": "Existing One",
                        "trackId": "AUS-NSW",
                        "country": "Australia",
                        "timezoneOffsetHours": 10,
                        "yearLevel": 10,
                        "interests": ["Genomics"],
                    }
                ],
                "tutor": {"id": 99, "name": ""},
            },
            "reason": "Shares interest 'genomics' with the group and has a close year level match.",
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
    ]
