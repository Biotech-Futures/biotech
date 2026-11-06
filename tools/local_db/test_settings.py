"""Disposable-container test settings; never load workstation credentials."""
import decouple
decouple.config = decouple.Config(decouple.RepositoryEmpty())
from config.settings_test_postgres import *  # noqa: F403
MEDIA_ROOT = '/tmp/biotech-demo-test-media'
EMAIL_FILE_PATH = '/tmp/biotech-demo-test-mail'
