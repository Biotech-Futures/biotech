# backend/conftest.py
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_local")

import django
django.setup()
