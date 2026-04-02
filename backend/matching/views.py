from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction, connection
from django.core.mail import send_mail
from django.conf import settings
from typing import Optional
import json

from .models import Student, StudentGroup, Mentor, Track

# ---------- Utility helpers ----------

@csrf_exempt
@require_POST
def reset_groups(request):
    """
    Reset group/mentor assignments with one click, and optionally reset the primary key auto-increment count.
    POST /api/reset_groups/?mode=<delete_all|clear_mentors|clear_members>&reset_seq=1

    parameter:
      - mode=delete_all      (Default) Delete all groups (including membership and mentor assignments)
      - mode=clear_mentors   Keep the group and members, and only clear the mentor
      - mode=clear_members   Keep the group, clear members (M2M) and mentors
      - reset_seq=1|0        Whether to try to reset the StudentGroup primary key sequence (default 1)
                              * SQLite: DELETE FROM sqlite_sequence WHERE name='matching_studentgroup';
                              * PostgreSQL: Automatically check the sequence and restart with 1
                              * MySQL: ALTER TABLE ... AUTO_INCREMENT = 1
    return:
      JSON result, including execution details and whether the sequence reset was successful.
    """
    mode = (request.GET.get("mode") or "delete_all").strip()
    reset_seq = (request.GET.get("reset_seq") or "1").lower() in ("1", "true", "yes")

    result = {"mode": mode}

    with transaction.atomic():
        if mode == "clear_mentors":
            n = StudentGroup.objects.update(mentor=None)
            result.update({"cleared_mentors": n})

        elif mode == "clear_members":
            cnt = 0
            for g in StudentGroup.objects.all():
                g.members.clear()
                g.interests.clear()
                g.mentor = None
                g.save(update_fields=["mentor"])
                cnt += 1
            result.update({"cleared_groups": cnt})

        else:  # delete_all
            count = StudentGroup.objects.count()
            StudentGroup.objects.all().delete()
            result.update({"deleted_groups": count})

        # —— Reset the auto-increment sequence (see database type) ——
        result["sequence_reset"] = False
        if reset_seq:
            vendor = connection.vendor  # 'sqlite' | 'postgresql' | 'mysql' | ...
            try:
                with connection.cursor() as cur:
                    if vendor == "sqlite":
                        # SQLite puts the auto-increment value of each table in sqlite_sequence
                        cur.execute("DELETE FROM sqlite_sequence WHERE name=%s", ["matching_studentgroup"])
                        result["sequence_reset"] = True

                    elif vendor == "postgresql":
                        # Automatically find the primary key sequence name, then RESTART
                        cur.execute("SELECT pg_get_serial_sequence(%s, %s)", ["matching_studentgroup", "id"])
                        row = cur.fetchone()
                        if row and row[0]:
                            seq = row[0]
                            cur.execute(f"ALTER SEQUENCE {seq} RESTART WITH 1")
                            result["sequence_reset"] = True

                    elif vendor == "mysql":
                        cur.execute("ALTER TABLE matching_studentgroup AUTO_INCREMENT = 1")
                        result["sequence_reset"] = True

                    else:
                        result["sequence_error"] = f"sequence reset not implemented for backend: {vendor}"
            except Exception as e:
                # Does not affect the main logic, just returns the error to let you know
                result["sequence_error"] = str(e)

    return JsonResponse(result, json_dumps_params={"ensure_ascii": False})

def _union_interests(members):
    """Return the union set of interests from a list of student members."""
    s = set()
    for m in members:
        for i in m.interests.all():
            s.add(i)
    return list(s)

def _chunk(lst, n):
    """Yield successive n-sized chunks from a list."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def _year_distance(a, b):
    """Absolute difference between two year levels."""
    return abs(int(a or 0) - int(b or 0))


# ---------- Auto grouping (primary pass) ----------

@csrf_exempt
def auto_group(_request):
    """
    Step 1: Build groups from preassigned Group Number (<=5 per group; overflow split)
    Step 2: For students without a preassigned number AND not in any group,
            group within the same track by shared interests (<=5)
    """
    created_from_preassigned = []
    created_auto = []

    with transaction.atomic():
        # Step 1. Preassigned groups
        pre_qs = (
            Student.objects
            .exclude(preassigned_group="")
            .prefetch_related("interests")
            .order_by("preassigned_group", "id")
        )

        # Bucket by group number (ignoring track by policy)
        bucket = {}
        for s in pre_qs:
            key = (s.preassigned_group or "").strip()
            if not key:
                continue
            bucket.setdefault(key, []).append(s)

        # Create groups (<=5; split overflow as GN, GN-1, GN-2 ...)
        for gnum, members in bucket.items():
            idx = 0
            for chunk in _chunk(members, 5):
                idx += 1
                name = gnum if idx == 1 else f"{gnum}-{idx}"
                if StudentGroup.objects.filter(name=name).exists():
                    continue
                grp = StudentGroup.objects.create(
                    name=name,
                    track=chunk[0].track,  # take the first member's track
                    year_min=min(m.year_level for m in chunk),
                    year_max=max(m.year_level for m in chunk),
                )
                grp.members.set(chunk)
                grp.interests.set(_union_interests(chunk))
                created_from_preassigned.append({
                    "group": grp.name,
                    "track": grp.track,
                    "size": len(chunk),
                    "members": [f"{m.first_name} {m.last_name}" for m in chunk],
                    "interests": [i.name for i in grp.interests.all()],
                })

        # Step 2. Interest-based grouping for the rest
        auto_qs = (
            Student.objects
            .filter(preassigned_group="")
            .filter(groups__isnull=True)
            .prefetch_related("interests")
        )

        # Bucket by track
        track_map = {}
        for s in auto_qs:
            track_map.setdefault(s.track, []).append(s)

        next_index = StudentGroup.objects.count() + 1

        for track, students in track_map.items():
            used = set()
            for s in students:
                if s.id in used:
                    continue
                base = set(i.id for i in s.interests.all())
                if not base:
                    # leave to fallback
                    continue

                grp = [s]
                for o in students:
                    if len(grp) == 5:
                        break
                    if o.id == s.id or o.id in used:
                        continue
                    other = set(i.id for i in o.interests.all())
                    if base & other:
                        grp.append(o)

                if len(grp) >= 2:
                    name = f"Group-{next_index}"
                    next_index += 1
                    g = StudentGroup.objects.create(
                        name=name, track=track,
                        year_min=min(m.year_level for m in grp),
                        year_max=max(m.year_level for m in grp),
                    )
                    g.members.set(grp)
                    g.interests.set(_union_interests(grp))
                    for m in grp:
                        used.add(m.id)
                    created_auto.append({
                        "group": g.name,
                        "track": g.track,
                        "size": len(grp),
                        "members": [f"{m.first_name} {m.last_name}" for m in grp],
                        "interests": [i.name for i in g.interests.all()],
                    })

    return JsonResponse(
        {"created_from_preassigned": created_from_preassigned, "created_auto": created_auto},
        json_dumps_params={"ensure_ascii": False},
    )


# ---------- Fallback grouping (remaining students) ----------

@csrf_exempt
def auto_group_fallback(_request):
    """
    Fallback for students still ungrouped:
      1) Within the same track, try shared-interest grouping again (<=5)
      2) Then greedy grouping by year-distance (GLOBAL prefers same country) (<=5)
    """
    created = []

    with transaction.atomic():
        qs = (Student.objects
              .filter(groups__isnull=True)
              .prefetch_related("interests")
              .order_by("track", "year_level", "country", "id"))

        # Bucket by track
        bucket = {}
        for s in qs:
            bucket.setdefault(s.track, []).append(s)

        next_index = StudentGroup.objects.count() + 1

        for track, students in bucket.items():
            used = set()

            # Pass 1: shared-interest groups
            for s in students:
                if s.id in used:
                    continue
                base = set(i.id for i in s.interests.all())
                if not base:
                    continue
                grp = [s]
                for o in students:
                    if len(grp) == 5:
                        break
                    if o.id in used or o.id == s.id:
                        continue
                    other = set(i.id for i in o.interests.all())
                    if base & other:
                        grp.append(o)
                if len(grp) >= 2:
                    g = StudentGroup.objects.create(
                        name=f"Group-{next_index}", track=track,
                        year_min=min(m.year_level for m in grp),
                        year_max=max(m.year_level for m in grp),
                    )
                    g.members.set(grp)
                    g.interests.set(_union_interests(grp))
                    for m in grp:
                        used.add(m.id)
                    next_index += 1
                    created.append({"name": g.name, "track": g.track, "size": len(grp)})

            # Pass 2: greedy by year/country proximity
            remain = [s for s in students if s.id not in used]
            remain.sort(key=lambda x: (x.year_level or 0, (x.country or "").upper(), x.id))

            i = 0
            while i < len(remain):
                if remain[i].id in used:
                    i += 1
                    continue
                seed = remain[i]
                grp = [seed]
                candidates = [x for x in remain if x.id not in used and x.id != seed.id]
                if track == Track.GLOBAL:
                    same_country = [x for x in candidates
                                    if (x.country or "").upper() == (seed.country or "").upper()]
                    others = [x for x in candidates if x not in same_country]
                    candidates = same_country + others
                candidates.sort(key=lambda x: _year_distance(x.year_level, seed.year_level))

                for o in candidates:
                    if len(grp) == 5:
                        break
                    grp.append(o)
                    used.add(o.id)

                if len(grp) >= 2:
                    used.add(seed.id)
                    g = StudentGroup.objects.create(
                        name=f"Group-{next_index}", track=track,
                        year_min=min(m.year_level for m in grp),
                        year_max=max(m.year_level for m in grp),
                    )
                    g.members.set(grp)
                    g.interests.set(_union_interests(grp))
                    next_index += 1
                    created.append({"name": g.name, "track": g.track, "size": len(grp)})
                i += 1

    return JsonResponse({"created_groups": created}, json_dumps_params={"ensure_ascii": False})


# ---------- Mentor assignment ----------


def _mentor_capacity_left(m: Mentor):
    """Remaining groups a mentor can take."""
    return max(0, int(m.max_groups or 0) - m.groups.count())

def _interest_overlap_score(group_interests, mentor_interests):
    """Number of overlapping interests."""
    return len(set(i.id for i in group_interests) & set(i.id for i in mentor_interests))

def _mentor_score(group, mentor):
    # Hard rule: at least 1 common interest
    g_int = set(group.interests.values_list("id", flat=True))
    m_int = set(mentor.interests.values_list("id", flat=True))
    inter = len(g_int & m_int)
    if inter == 0:
        return -1000

    score = inter * 100

    # Minor tie-break: GLOBAL + "first student" and mentor same country +1
    first_student = group.members.first()
    if group.track == Track.GLOBAL and first_student:
        if (first_student.country or "").strip().lower() == (mentor.country or "").strip().lower():
            score += 1

    return score


@csrf_exempt
def assign_mentors(_request):
    """
    Assign a mentor to groups without one:
      - Candidate pool by track rule
      - Hard rule: at least one overlapping interest
      - Respect mentor capacity (max_groups)
      - Choose highest score within the first non-empty candidate layer
    """
    assigned = []
    skipped = []

    with transaction.atomic():
        groups = (StudentGroup.objects
                  .filter(mentor__isnull=True)
                  .prefetch_related("members", "interests")
                  .order_by("track", "name"))

        for g in groups:
            # Candidate layers by track policy
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
                        if _mentor_capacity_left(m) > 0
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
                assigned.append({
                    "group": g.name, "track": g.track,
                    "mentor": f"{selected.first_name} {selected.last_name}",
                    "background": selected.background,
                    "remaining_capacity": _mentor_capacity_left(selected),
                })
            else:
                skipped.append({"group": g.name, "track": g.track, "reason": "no_available_mentor"})

    return JsonResponse({"assigned": assigned, "skipped": skipped}, json_dumps_params={"ensure_ascii": False})


# ---------- Simple health check (optional) ----------

def health(_request):
    """Simple health endpoint."""
    return JsonResponse({"status": "ok"})


# ---------- Mentor replacement, deactivation, and bulk placeholders ----------

def _get_json_body(request: HttpRequest):
    try:
        return json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        return {}

def _notify_replacement(group: StudentGroup, old_mentor: Optional[Mentor], new_mentor: Optional[Mentor]):
    subject = f"Mentor update for group {group.name}"
    lines = [f"Group: {group.name}"]
    if old_mentor:
        lines.append(f"Old mentor: {old_mentor.first_name} {old_mentor.last_name} <{old_mentor.email}>")
    if new_mentor:
        lines.append(f"New mentor: {new_mentor.first_name} {new_mentor.last_name} <{new_mentor.email}>")
    message = "\n".join(lines)

    # Collect recipients: group students, their supervisors (if any), old mentor, new mentor
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


@csrf_exempt
@require_POST
def replace_group_mentor(request: HttpRequest):
    """
    POST /api/replace_group_mentor/
    Body JSON: {"group_id": int, "new_mentor_id": int}
    Reassign the group's mentor, notify affected parties.
    """
    data = _get_json_body(request)
    group_id = int(data.get("group_id")) if data.get("group_id") is not None else None
    mentor_id = int(data.get("new_mentor_id")) if data.get("new_mentor_id") is not None else None
    if not group_id or not mentor_id:
        return JsonResponse({"error": "group_id and new_mentor_id are required"}, status=400)

    with transaction.atomic():
        try:
            group = StudentGroup.objects.select_related("mentor").prefetch_related("members").get(id=group_id)
            new_mentor = Mentor.objects.get(id=mentor_id)
        except StudentGroup.DoesNotExist:
            return JsonResponse({"error": "group not found"}, status=404)
        except Mentor.DoesNotExist:
            return JsonResponse({"error": "mentor not found"}, status=404)

        old_mentor = group.mentor
        group.mentor = new_mentor
        group.save(update_fields=["mentor"])

        _notify_replacement(group, old_mentor, new_mentor)

        return JsonResponse({
            "group": group.name,
            "old_mentor": (f"{old_mentor.first_name} {old_mentor.last_name}" if old_mentor else None),
            "new_mentor": f"{new_mentor.first_name} {new_mentor.last_name}",
        }, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
@require_POST
def deactivate_mentor(request: HttpRequest):
    """
    POST /api/deactivate_mentor/
    Body JSON: {"mentor_id": int}
    Mark mentor as inactive and clear their groups' mentor assignment.
    """
    data = _get_json_body(request)
    mentor_id = int(data.get("mentor_id")) if data.get("mentor_id") is not None else None
    if not mentor_id:
        return JsonResponse({"error": "mentor_id is required"}, status=400)

    with transaction.atomic():
        try:
            mentor = Mentor.objects.get(id=mentor_id)
        except Mentor.DoesNotExist:
            return JsonResponse({"error": "mentor not found"}, status=404)

        groups = list(mentor.groups.all())
        mentor.is_active = False
        mentor.save(update_fields=["is_active"])
        for g in groups:
            old = g.mentor
            g.mentor = None
            g.save(update_fields=["mentor"])
            _notify_replacement(g, old, None)

    return JsonResponse({"deactivated": mentor_id, "cleared_groups": [g.name for g in groups]})


@csrf_exempt
def bulk_inactive_mentors_preview(_request: HttpRequest):
    """
    GET /api/bulk_inactive_mentors_preview/
    Placeholder: return mentors considered inactive (currently empty, returns schema only).
    """
    # Future: compute by engagement metrics. For now return empty with structure.
    return JsonResponse({
        "inactive_candidates": [],
        "criteria": "placeholder; to be implemented",
    }, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
@require_POST
def bulk_replace_inactive_mentors(request: HttpRequest):
    """
    POST /api/bulk_replace_inactive_mentors/
    Body JSON placeholder: {"strategy": "auto|manual", "mapping": [{"old_id": x, "new_id": y}]}
    For now, no-op except validation and schema.
    """
    _ = _get_json_body(request)
    return JsonResponse({"status": "placeholder", "reassigned": [], "deactivated": []})
