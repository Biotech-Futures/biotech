from django.db import models


class SendEmail(models.Model):
    recipients = models.TextField("Recipients", help_text="Multiple email addresses separated by commas or spaces")
    subject = models.CharField("Subject", max_length=255)
    body = models.TextField("Body")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Send Email"
        verbose_name_plural = "Send Emails"

    def __str__(self) -> str:
        return f"Email to {self.recipients}"


