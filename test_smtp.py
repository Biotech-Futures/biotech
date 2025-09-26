"""Standalone SMTP test using Django settings.

Run: python test_smtp.py
"""
"""
***IMPORTANT******IMPORTANT******IMPORTANT******IMPORTANT******IMPORTANT******IMPORTANT******IMPORTANT***
This file is only used to test the email sending function and has nothing to do with the system function
***IMPORTANT******IMPORTANT******IMPORTANT******IMPORTANT******IMPORTANT******IMPORTANT******IMPORTANT***

"""
import os
import sys
import django
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
# Make sure backend is in sys.path
backend_dir = BASE_DIR / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# The correct Django settings module is core.settings (not backend.settings)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.core.mail import get_connection, EmailMessage
from django.conf import settings

print("BACKEND:", settings.EMAIL_BACKEND)
print("HOST:", settings.EMAIL_HOST, "PORT:", settings.EMAIL_PORT,
      "TLS:", settings.EMAIL_USE_TLS, "SSL:", settings.EMAIL_USE_SSL)
print("USER:", settings.EMAIL_HOST_USER, "FROM:", settings.DEFAULT_FROM_EMAIL)

conn = None
try:
    print("\nTrying to connect to SMTP server...")
    conn = get_connection(fail_silently=False)
    conn.open()
    print("Connection opened successfully.")

    if hasattr(conn, "connection") and conn.connection:
        conn.connection.set_debuglevel(1)

    msg = EmailMessage(
        subject="SMTP Authentication Test",
        body="This is a test email from Django.",
        from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
        to=[settings.EMAIL_HOST_USER],  #Send to your own mailbox for easy verification
        connection=conn,
    )

    print("Sending email...")
    ok = msg.send()
    print("send result:", ok)

except Exception as e:
    print(f"\nAn error occurred: {e}")

finally:
    if conn:
        print("Closing connection...")
        conn.close()
    print("Finished.")