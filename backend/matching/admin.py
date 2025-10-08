from django.contrib import admin
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
from .models import Interest, Student, StudentGroup, Mentor
from .models import Track

class NoAddMixin(admin.ModelAdmin):
    # Completely disable adding: sidebar/list page buttons/direct access to /add/ will be blocked
    def has_add_permission(self, request):
        return False

    # Prevent Admin homepage/app page from showing "+ Add" links
    def get_model_perms(self, request):
        perms = super().get_model_perms(request)
        perms["add"] = False
        return perms


# ---- Helpers to pretty print ----
def _group_names(obj):
    return ", ".join(g.name for g in obj.groups.all())

def _mentor_names(obj):
    names = []
    for g in obj.groups.all():
        if g.mentor:
            names.append(f"{g.mentor.first_name} {g.mentor.last_name}")
    return ", ".join(sorted(set(names))) or "-"

def _student_names(group):
    return ", ".join(f"{s.first_name} {s.last_name}" for s in group.members.all())

# ---- Admin registrations ----

# ---- Scoring helpers (aligned with API /assign_mentors) ----


def _interest_overlap_score(group_interests, mentor_interests):
    return len(set(i.id for i in group_interests) & set(i.id for i in mentor_interests))

def _mentor_score(group, mentor):
    overlap = _interest_overlap_score(group.interests.all(), mentor.interests.all())
    if overlap == 0:
        return -1000
    score = overlap * 100
    # GLOBAL groups + same country +1 (can be kept or removed)
    s = group.members.first()
    if group.track == Track.GLOBAL and s and (s.country or "").strip().lower() == (mentor.country or "").strip().lower():
        score += 1
    return score

@admin.register(Interest)
class InterestAdmin(NoAddMixin, admin.ModelAdmin):
    search_fields = ["name"]
    list_display = ["id", "name"]

@admin.register(Student)
class StudentAdmin(NoAddMixin, admin.ModelAdmin):
    # Display: basic information + group + mentor
    list_display = [
        "id", "first_name", "last_name", "email",
        "year_level", "track", "country", "region",
        "preassigned_group", "groups_list", "mentors_list",
    ]
    list_filter = ["track", "year_level", "country", "region", "preassigned_group"]
    search_fields = ["first_name", "last_name", "email", "school"]
    readonly_fields = ["groups_list", "mentors_list"]  # Details page also displays

    def groups_list(self, obj):
        return _group_names(obj)
    groups_list.short_description = "Groups"

    def mentors_list(self, obj):
        return _mentor_names(obj)
    mentors_list.short_description = "Mentors"

@admin.register(StudentGroup)
class StudentGroupAdmin(NoAddMixin, admin.ModelAdmin):
    # Display: basic information + number of members + mentors + member list
    list_display = ["id", "name", "track", "year_min", "year_max", "mentor", "member_count", "members_list"]
    list_filter = ["track", "mentor"]
    search_fields = ["name"]
    filter_horizontal = ["members", "interests"]  # On the group details page, use the left and right columns to select members/interests
    actions = ["action_replace_group_mentor"]
    change_list_template = "admin/matching/studentgroup/change_list.html"

    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = "#Members"

    def members_list(self, obj):
        return _student_names(obj)
    members_list.short_description = "Members"

    def _notify_replacement(self, group, old_mentor, new_mentor):
        subject = f"Mentor update for group {group.name}"
        lines = [f"Group: {group.name}"]
        if old_mentor:
            lines.append(f"Old mentor: {old_mentor.first_name} {old_mentor.last_name} <{old_mentor.email}>")
        if new_mentor:
            lines.append(f"New mentor: {new_mentor.first_name} {new_mentor.last_name} <{new_mentor.email}>")
        message = "\n".join(lines)

        recipients = set()
        for s in group.members.all():
            if s.email:
                recipients.add(s.email)
            if (s.supervisor_email or "").strip():
                recipients.add(s.supervisor_email.strip())
        if old_mentor and old_mentor.email:
            recipients.add(old_mentor.email)
        if new_mentor and new_mentor.email:
            recipients.add(new_mentor.email)
        if recipients:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                list(recipients),
                fail_silently=not settings.DEBUG,
            )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "replace-mentor/",
                self.admin_site.admin_view(self.replace_mentor_view),
                name="matching_studentgroup_replace_mentor",
            ),
            path(
                "reassign-mentors/",
                self.admin_site.admin_view(self.reassign_mentors_view),
                name="matching_studentgroup_reassign_mentors",
            ),
        ]
        return custom + urls

    def action_replace_group_mentor(self, request, queryset):
        selected = request.POST.getlist(ACTION_CHECKBOX_NAME)
        if not selected:
            self.message_user(request, "Please select at least one group first", level=messages.WARNING)
            return
        return redirect(f"./replace-mentor/?ids={','.join(selected)}")
    action_replace_group_mentor.short_description = "Replace the mentor for the selected group (send email)"

    def replace_mentor_view(self, request):
        ids_param = request.GET.get("ids", "")
        group_ids = [int(x) for x in ids_param.split(",") if x.strip().isdigit()]
        from .models import Mentor, StudentGroup
        groups = StudentGroup.objects.filter(id__in=group_ids)

        if request.method == "POST":
            mentor_id = request.POST.get("new_mentor_id")
            if not mentor_id:
                messages.error(request, "Please fill in the new mentor ID")
            else:
                try:
                    mentor = Mentor.objects.get(id=int(mentor_id))
                except (ValueError, Mentor.DoesNotExist):
                    messages.error(request, "Invalid new mentor ID")
                else:
                    # Calculate capacity and candidate groups
                    current_load = mentor.groups.count()
                    capacity_left = max(0, int(mentor.max_groups or 0) - current_load)
                    target_groups = groups.select_related("mentor").prefetch_related("members", "interests")
                    # Filter out groups that already have this mentor
                    candidates = [g for g in target_groups if not (g.mentor and g.mentor.id == mentor.id)]

                    if capacity_left == 0:
                        messages.error(
                            request,
                            (
                                f"Mentor ID={mentor.id} has no remaining capacity: "
                                f"current_load={current_load}, max={mentor.max_groups}."
                            ),
                        )
                        return redirect("..")

                    # Sort by matching score (same rules as /assign_mentors), first remove groups with no interest overlap
                    scored = []
                    no_overlap = []
                    for g in candidates:
                        overlap = _interest_overlap_score(g.interests.all(), mentor.interests.all())
                        if overlap <= 0:
                            no_overlap.append(g)
                            continue
                        scored.append((g, _mentor_score(g, mentor)))

                    if not scored:
                        messages.error(request, "No eligible groups share interests with the selected mentor.")
                        return redirect("..")

                    scored.sort(key=lambda x: x[1], reverse=True)

                    to_assign = [g for g, _ in scored[:capacity_left]]
                    skipped_by_capacity = [g for g, _ in scored[capacity_left:]]

                    with transaction.atomic():
                        for g in to_assign:
                            old = g.mentor
                            g.mentor = mentor
                            g.save(update_fields=["mentor"])
                            self._notify_replacement(g, old, mentor)

                    assigned_count = len(to_assign)
                    msg = (
                        f"Assigned {assigned_count} group(s) to mentor ID={mentor.id}. "
                        f"Capacity left after assignment: {max(capacity_left - assigned_count, 0)}."
                    )
                    if skipped_by_capacity:
                        msg += f" Skipped {len(skipped_by_capacity)} group(s) due to capacity limit."
                    if no_overlap:
                        msg += f" Skipped {len(no_overlap)} group(s) due to no shared interests."
                    self.message_user(request, msg, level=messages.INFO)
                    return redirect("..")

        context = dict(
            self.admin_site.each_context(request),
            title="Replace the mentor of the selected group",
            groups=groups,
        )
        return render(request, "admin/matching/replace_group_mentor.html", context)

    def reassign_mentors_view(self, request):
        # Reassign mentors for groups without mentors, reusing rules consistent with /api/assign_mentors/
        assigned = 0
        skipped = 0
        with transaction.atomic():
            groups = (StudentGroup.objects
                      .filter(mentor__isnull=True)
                      .prefetch_related("members", "interests")
                      .order_by("track", "name"))

            for g in groups:
                # Candidate layer by track policy
                if g.track in {Track.AUS_NSW, Track.AUS_QLD, Track.AUS_VIC, Track.AUS_WA, Track.BRA}:
                    layers = [
                        Mentor.objects.filter(track=g.track),
                        Mentor.objects.filter(track=Track.GLOBAL),
                        Mentor.objects.exclude(track__in=[g.track, Track.GLOBAL]),
                    ]
                else:
                    layers = [
                        Mentor.objects.filter(track=Track.GLOBAL),
                        Mentor.objects.exclude(track=Track.GLOBAL),
                    ]

                selected = None
                best_score = -10**9
                for layer in layers:
                    pool = [m for m in layer.prefetch_related("interests")
                            if (m.max_groups or 0) - m.groups.count() > 0
                            and _interest_overlap_score(g.interests.all(), m.interests.all()) > 0]
                    if not pool:
                        continue
                    for m in pool:
                        score = _mentor_score(g, m)
                        if score > best_score:
                            selected, best_score = m, score
                    if selected:
                        break

                if selected:
                    g.mentor = selected
                    g.save(update_fields=["mentor"])
                    assigned += 1
                else:
                    skipped += 1

        self.message_user(
            request,
            f"Reassignment completed. Assigned={assigned}, Skipped={skipped} (no available mentor)",
            level=messages.INFO,
        )
        return redirect("..")

@admin.register(Mentor)
class MentorAdmin(NoAddMixin, admin.ModelAdmin):
    # Display: mentor's basic knowledge + number of groups taught
    list_display = ["id", "first_name", "last_name", "email", "track", "background", "max_groups", "current_load", "groups_list"]
    list_filter = ["track", "background", "country"]
    search_fields = ["first_name", "last_name", "email", "institution"]
    actions = ["action_deactivate_mentors"]

    def current_load(self, obj):
        return obj.groups.count()
    current_load.short_description = "Groups assigned"

    def groups_list(self, obj):
        return ", ".join(g.name for g in obj.groups.all()) or "-"
    groups_list.short_description = "Group names"

    def action_deactivate_mentors(self, request, queryset):
        from .models import StudentGroup
        count = 0
        with transaction.atomic():
            for mentor in queryset:
                groups = list(mentor.groups.all())
                mentor.is_active = False
                mentor.save(update_fields=["is_active"])
                # Notify the mentor that his/her account has been deactivated
                if mentor.email:
                    try:
                        send_mail(
                            subject="Your mentor account has been deactivated",
                            message=(
                                "Hello {first} {last},\n\n"
                                "Your mentor account has been deactivated by the administrator. "
                                "If you believe this is a mistake, please contact support.\n\n"
                                "Regards,\nAdmin"
                            ).format(first=mentor.first_name, last=mentor.last_name),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[mentor.email],
                            fail_silently=not settings.DEBUG,
                        )
                    except Exception:
                        if settings.DEBUG:
                            raise
                for g in groups:
                    old = g.mentor
                    g.mentor = None
                    g.save(update_fields=["mentor"])
                    # notify similar to above
                    subject = f"Mentor update for group {g.name}"
                    lines = [f"Group: {g.name}"]
                    if old:
                        lines.append(f"Old mentor: {old.first_name} {old.last_name} <{old.email}>")
                    message = "\n".join(lines)
                    recipients = set()
                    for s in g.members.all():
                        if s.email:
                            recipients.add(s.email)
                        if (s.supervisor_email or "").strip():
                            recipients.add(s.supervisor_email.strip())
                    if old and old.email:
                        recipients.add(old.email)
                    if recipients:
                        send_mail(
                            subject,
                            message,
                            settings.DEFAULT_FROM_EMAIL,
                            list(recipients),
                            fail_silently=not settings.DEBUG,
                        )
                count += 1
        self.message_user(request, f"Disabled  {count} mentors, and cleared the group mentor field for all associated groups.")


