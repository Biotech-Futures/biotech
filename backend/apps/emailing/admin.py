from django.contrib import admin, messages
from django.core.mail import EmailMultiAlternatives
from django.utils.translation import gettext_lazy as _

from .forms import SendEmailForm
from .models import SendEmail
from matching.models import Mentor, Student, Track


@admin.register(SendEmail)
class SendEmailAdmin(admin.ModelAdmin):
    list_display = ("subject", "created_at")
    fields = ("recipients", "subject", "body", "created_at")
    readonly_fields = ("recipients", "subject", "body", "created_at")

    def has_view_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def add_view(self, request, form_url="", extra_context=None):
        # Use custom send form, send email and save record for history after submission
        # Dynamically build filtered results choices
        def _build_filtered_choices(people_type: str, track: str):
            emails = []
            if people_type in ("mentor", "both", ""):
                qs = Mentor.objects.all()
                if track:
                    qs = qs.filter(track=track)
                emails.extend([(m.email, f"Mentor | {m.first_name} {m.last_name} <{m.email}>") for m in qs if m.email])
            if people_type in ("student", "both", ""):
                qs = Student.objects.all()
                if track:
                    qs = qs.filter(track=track)
                emails.extend([(s.email, f"Student | {s.first_name} {s.last_name} <{s.email}>") for s in qs if s.email])
            # Remove duplicates while maintaining order
            seen = set()
            dedup = []
            for v, label in emails:
                if v in seen:
                    continue
                seen.add(v)
                dedup.append((v, label))
            return dedup

        if request.method == "POST":
            form = SendEmailForm(request.POST)
            # Build filtered results based on request
            people_type = (request.POST.get("people_type") or "").strip()
            track = (request.POST.get("track") or "").strip()
            form.fields["selected_recipients"].choices = _build_filtered_choices(people_type, track)
            if form.is_valid():
                recipients_list = form.cleaned_data["recipients"]
                subject = form.cleaned_data["subject"]
                body = form.cleaned_data["body"]
                selected = form.cleaned_data.get("selected_recipients") or []
                final_recipients = list({*recipients_list, *selected})
                if not final_recipients:
                    messages.error(request, _("Please select at least one recipient (manual or filtered)"))
                    from django.shortcuts import redirect
                    return redirect("admin:emailing_sendemail_add")
                try:
                    # Generate personalized email for each recipient
                    for recipient_email in final_recipients:
                        # Get recipient's first_name
                        first_name = None
                        try:
                            # First try to find in Mentor table
                            mentor = Mentor.objects.get(email=recipient_email)
                            first_name = mentor.first_name
                        except Mentor.DoesNotExist:
                            try:
                                # If not found in Mentor table, try Student table
                                student = Student.objects.get(email=recipient_email)
                                first_name = student.first_name
                            except Student.DoesNotExist:
                                # If not found in either, use username part of email address
                                first_name = recipient_email.split('@')[0]
                        
                        # Generate personalized email body
                        personalized_body = f"Dear {first_name},\n\n{body}"
                        
                        message = EmailMultiAlternatives(
                            subject=subject,
                            body=personalized_body,
                            from_email=None,
                            to=[recipient_email],
                        )
                        # Add plain text fallback version and HTML version (rich text)
                        message.attach_alternative(personalized_body, "text/html")
                        
                        # Handle attachments (multiple files)
                        for file in request.FILES.getlist("attachments"):
                            message.attach(file.name, file.read(), file.content_type)
                        
                        # Send individual email
                        message.send(fail_silently=False)
                    
                    sent = len(final_recipients)  # Number of emails sent
                    # Save to database as history record (save HTML body)
                    SendEmail.objects.create(
                        recipients=", ".join(final_recipients), subject=subject, body=body
                    )
                    messages.success(request, _("Emails sent: {count}").format(count=sent))
                except Exception as exc:
                    messages.error(request, _("Send failed: {err}").format(err=str(exc)))
                from django.shortcuts import redirect

                # Return to list after sending for history viewing
                return redirect("admin:emailing_sendemail_changelist")
        else:
            form = SendEmailForm()
            form.fields["selected_recipients"].choices = _build_filtered_choices("", "")

        from django.template.response import TemplateResponse

        context = {
            **self.admin_site.each_context(request),
            "title": _("Send email"),
            "opts": self.model._meta,
            "app_label": self.model._meta.app_label,
            "form": form,
            "is_popup": False,
            "save_as": False,
            "has_view_permission": True,
            "has_add_permission": True,
            "has_change_permission": False,
            "has_delete_permission": False,
        }
        return TemplateResponse(request, "admin/emailing/send_email.html", context)


