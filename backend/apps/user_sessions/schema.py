from drf_spectacular.extensions import OpenApiAuthenticationExtension


class SessionIdAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.user_sessions.auth.SessionIdAuthentication"
    name = "SessionIdAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "X-Session-Id",
            "description": "Session ID supplied via X-Session-Id header. The backend also accepts the sid cookie at runtime.",
        }
