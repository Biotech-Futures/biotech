# apps/user_sessions/middleware.py
from .models import Sessions


class SessionTrackingMiddleware:
    """
    Middleware to track user sessions in the Sessions model for analytics.
    Records authenticated requests to track user activity.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Track authenticated requests
        if request.user.is_authenticated:
            # Create a session tracking record
            Sessions.objects.create(
                user=request.user,
                isloggedin=True
            )

        return response
