"""Deploy-configuration system checks.

Registered from :class:`apps.services.apps.ServicesConfig.ready`, so they run
on every ``runserver`` start, ``migrate`` and ``manage.py check``.
"""
from django.conf import settings
from django.core.checks import Warning, register


@register()
def azure_storage_credentials_check(app_configs, **kwargs):
    """Warn loudly when Azure storage is on but cannot possibly work.

    ``config.settings`` pins ``USE_AZURE_BLOB_STORAGE = True`` (prod), while
    dev uses ``settings_local`` to flip it off. Running the prod settings
    without Azure credentials does NOT crash: uploads fail at request time and
    URL signing quietly degrades to ``file_url: null`` (see
    ``ManagedFileService.resolve_url``), which surfaces as blank previews in
    the marking UI with nothing in the console. This check turns that silent
    misconfiguration into a startup warning — the usual cause locally is
    starting ``runserver`` without ``--settings=config.settings_local``.
    """
    if not getattr(settings, "USE_AZURE_BLOB_STORAGE", False):
        return []

    has_connection_string = bool(getattr(settings, "AZURE_CONNECTION_STRING", ""))
    has_account_key = bool(
        getattr(settings, "AZURE_ACCOUNT_NAME", "")
        and getattr(settings, "AZURE_ACCOUNT_KEY", "")
    )
    if has_connection_string or has_account_key:
        return []

    return [
        Warning(
            "USE_AZURE_BLOB_STORAGE is on but no Azure credentials are set "
            "(neither AZURE_CONNECTION_STRING nor AZURE_ACCOUNT_NAME + "
            "AZURE_ACCOUNT_KEY). File uploads will fail and file URLs will "
            "resolve to null (blank previews) at request time.",
            hint=(
                "Local dev: run with --settings=config.settings_local (uses "
                "MEDIA_ROOT file storage). Deploys: set AZURE_CONNECTION_STRING "
                "(or AZURE_ACCOUNT_NAME + AZURE_ACCOUNT_KEY) in the environment."
            ),
            id="services.W001",
        )
    ]
