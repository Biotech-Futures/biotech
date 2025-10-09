from django import forms
from matching.models import Track


class SendEmailForm(forms.Form):
    recipients = forms.CharField(
        label="Recipients",
        help_text="Multiple email addresses separated by commas or spaces",
        widget=forms.Textarea(attrs={"rows": 2}),
        required=False,
    )
    subject = forms.CharField(label="Subject", max_length=255)
    body = forms.CharField(label="Body", widget=forms.Textarea(attrs={"rows": 8}))
    class MultipleFileInput(forms.FileInput):
        allow_multiple_selected = True

    attachments = forms.FileField(
        label="Attachments",
        widget=MultipleFileInput(attrs={"multiple": True}),
        required=False,
        help_text="Optional, supports multiple files: images, archives, documents, etc.",
    )

    # Filters
    PEOPLE_CHOICES = (
        ("mentor", "Mentor"),
        ("student", "Student"),
        ("both", "Both"),
    )
    people_type = forms.ChoiceField(label="People type", choices=PEOPLE_CHOICES, required=False)
    track = forms.ChoiceField(label="Track", required=False)

    # Checkbox list of filtered recipients (emails)
    selected_recipients = forms.MultipleChoiceField(
        label="Filtered Results",
        required=False,
        choices=(),
        widget=forms.CheckboxSelectMultiple,
        help_text="Selected recipients will be merged with manual recipients above",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # dynamic Track choices from enum
        track_choices = [("", "All")] + [(t.value, t.label) for t in Track]
        self.fields["track"].choices = track_choices

    def clean_recipients(self):
        value = self.cleaned_data["recipients"]
        tokens = [t.strip() for t in value.replace("\n", " ").replace(",", " ").split(" ") if t.strip()]
        if not tokens:
            # Allow empty, provided by selected_recipients
            return []
        # Simple email validation, relies on Django's EmailValidator
        from django.core.validators import EmailValidator

        validator = EmailValidator()
        cleaned = []
        for email in tokens:
            validator(email)
            cleaned.append(email)
        return cleaned


