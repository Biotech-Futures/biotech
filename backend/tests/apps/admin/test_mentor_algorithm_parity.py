from apps.admin.algorithms.mentor import compute_interest_bonus, match_mentors
from apps.admin.services import mentor_match


def test_interest_bonus_matches_typescript_math_round():
    assert compute_interest_bonus(
        ["Genomics", "AI", "Vaccines"],
        ["genomics", "ai", "vaccines", "Climate"],
    ) == 23


def test_balanced_mentor_recommendations_match_typescript_shape():
    recommendations = match_mentors(
        [
            {
                "groupId": 10,
                "groupName": "NSW Bio",
                "countryName": "Australia",
                "utcOffsetHours": 10.0,
                "studentInterests": ["Genomics", "AI", "Vaccines", "Climate"],
                "studentCount": 3,
            }
        ],
        [
            {
                "mentorId": 20,
                "firstName": "Maya",
                "lastName": "Chen",
                "countryName": "Australia",
                "utcOffsetHours": 10.0,
                "institution": "UTS",
                "interests": ["Genomics", "AI", "Vaccines"],
                "maxGroupCount": 2,
                "currentAcceptedCount": 0,
            }
        ],
        "balanced",
    )

    assert recommendations == [
        {
            "group": {
                "groupId": 10,
                "groupName": "NSW Bio",
                "countryName": "Australia",
                "utcOffsetHours": 10.0,
                "studentInterests": ["Genomics", "AI", "Vaccines", "Climate"],
                "studentCount": 3,
            },
            "recommendedMentor": {
                "mentorId": 20,
                "name": "Maya Chen",
                "countryName": "Australia",
                "institution": "UTS",
                "interests": ["Genomics", "AI", "Vaccines"],
                "remainingCapacity": 1,
            },
            "reason": "Country match: Australia. Shared interests: Genomics, AI, Vaccines",
            "score": 127,
            "scoreBreakdown": {
                "baseScore": 100,
                "countryPenalty": 0,
                "interestBonus": 23,
                "timezonePenalty": 0,
                "capacityBonus": 4,
                "objectiveScore": 127,
            },
        }
    ]


def test_balanced_returns_null_recommendation_for_no_shared_interests():
    recommendations = match_mentors(
        [
            {
                "groupId": 11,
                "groupName": "No Overlap",
                "countryName": "Australia",
                "utcOffsetHours": 10.0,
                "studentInterests": ["Climate"],
                "studentCount": 2,
            }
        ],
        [
            {
                "mentorId": 21,
                "firstName": "Noah",
                "lastName": "Singh",
                "countryName": "Australia",
                "utcOffsetHours": 10.0,
                "institution": None,
                "interests": ["Genomics"],
                "maxGroupCount": 1,
                "currentAcceptedCount": 0,
            }
        ],
        "balanced",
    )

    assert recommendations[0]["recommendedMentor"] is None
    assert recommendations[0]["group"]["groupId"] == 11
    assert recommendations[0]["score"] == 0


def test_mentor_match_mentor_list_reuses_admin_mentor_response(monkeypatch):
    expected = [
        {
            "mentorId": 1,
            "firstName": "Maya",
            "lastName": "Chen",
            "name": "Maya Chen",
            "email": "maya@example.com",
            "isActive": True,
            "institution": "UTS",
            "countryName": "Australia",
            "utcOffsetHours": 10.0,
            "maxGroupCount": 2,
            "currentAssignedCount": 1,
            "remainingCapacity": 1,
            "interests": ["Genomics"],
            "lastMessageAt": None,
            "availability": [],
            "certificates": [],
        }
    ]

    monkeypatch.setattr(
        mentor_match, "get_mentor_list", lambda requesting_user=None: expected
    )

    assert mentor_match.get_mentors() == expected
