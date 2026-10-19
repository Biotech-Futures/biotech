from django.apps import AppConfig


class ManagementConfig(AppConfig):
    """Running the competition: the deadline and extensions, releasing
    results, the documents, and the finalist and results emails."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.management"
