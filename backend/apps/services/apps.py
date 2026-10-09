from django.apps import AppConfig


class ServicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.services'

    def ready(self):
        # Registers deploy-configuration system checks (Azure storage creds).
        from . import checks  # noqa: F401