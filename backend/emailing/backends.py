from django.core.mail.backends.console import EmailBackend as ConsoleEmailBackend
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend


class DualEmailBackend:
    """
    Custom email backend that sends emails to both console and SMTP.
    Useful for debugging while still sending real emails.
    """

    def __init__(self, *args, **kwargs):
        self.console_backend = ConsoleEmailBackend(*args, **kwargs)
        self.smtp_backend = SMTPEmailBackend(*args, **kwargs)

    def send_messages(self, email_messages):
        """Send messages through both console and SMTP backends"""
        # Send to console for debugging
        console_sent = self.console_backend.send_messages(email_messages)

        # Send via SMTP (SendGrid)
        smtp_sent = self.smtp_backend.send_messages(email_messages)

        # Return the number sent via SMTP (primary backend)
        return smtp_sent

    def open(self):
        """Open both backends"""
        self.console_backend.open()
        self.smtp_backend.open()

    def close(self):
        """Close both backends"""
        self.console_backend.close()
        self.smtp_backend.close()
