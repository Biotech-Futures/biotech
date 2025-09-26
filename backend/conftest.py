# backend/conftest.py
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

# If your project name is not core, please change the above to "<your project name>.settings"

import django
django.setup()
