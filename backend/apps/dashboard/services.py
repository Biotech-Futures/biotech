def get_dashboard_summary(user):
    """
    All dashboard business logic lives here.
    Views must never compute data directly.
    """
    return {
        "user": user.username,
        "stats": {
            "tasks": 0,
            "events": 0,
            "groups": 0,
        }
    }