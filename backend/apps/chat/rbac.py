from __future__ import annotations

from django.apps import apps
from django.contrib.auth import get_user_model
from apps.common.rbac import (
    group_participant_qs,
    is_admin,
)


def _group_from_value(group):
    if group is None:
        return None
    if hasattr(group, "id"):
        # Deleted groups must not authorize chat access from cached model instances.
        if getattr(group, "deleted_at", None) is not None:
            return None
        return group

    Groups = apps.get_model("groups", "Groups")
    group_id = getattr(group, "id", group)
    return Groups.objects.only("id").filter(
        pk=group_id,
        deleted_at__isnull=True,
    ).first()


def can_access_chat_group(user, group) -> bool:
    if not user or not user.is_authenticated:
        return False

    target_group = _group_from_value(group)
    if target_group is None:
        return False

    if is_admin(user):
        return True

    return group_participant_qs(user, target_group.id).exists()


def chat_recipients_qs(group_id, *, exclude_user_id=None):
    """Members of ``group_id`` a message is actually addressed to.

    Role/status predicate matches the unread digest (``services/digest.py``,
    which additionally scopes to non-deleted groups): supervisors observe
    rather than participate, and login-blocked accounts can never open the
    board. Counting either makes "read by everyone" unreachable.
    ``invited``/``pending`` users DO count — they are ``is_active=False``
    but can still sign in.
    """
    GroupMembership = apps.get_model("groups", "GroupMembership")
    User = get_user_model()
    queryset = (
        GroupMembership.objects
        .filter(group_id=group_id, left_at__isnull=True)
        .exclude(membership_role=GroupMembership.MembershipRoleChoices.SUPERVISOR)
        .exclude(user__account_status__in=User.INACTIVE_LOGIN_STATUSES)
        .select_related("user")
    )
    if exclude_user_id is not None:
        queryset = queryset.exclude(user_id=exclude_user_id)
    return queryset


def _is_group_mentor(user, group_id) -> bool:
    """Active mentor membership in this specific group.

    Scoped deliberately: mentoring one group is not a licence to moderate
    another, so the role alone never grants anything.
    """
    return group_participant_qs(user, group_id).filter(
        membership_role="mentor",
    ).exists()


def _was_sent_by_a_student(message, group_id) -> bool:
    """The sender takes part in this group as a student.

    Read off the membership rather than the profile: a mentor who also holds a
    StudentProfile elsewhere is still a mentor here, and the rule is about the
    role someone is playing in this group.
    """
    GroupMembership = apps.get_model("groups", "GroupMembership")
    return GroupMembership.objects.filter(
        group_id=group_id,
        user_id=getattr(message, "sender_user_id", None),
        left_at__isnull=True,
        membership_role="student",
    ).exists()


def can_moderate_chat_message(user, message) -> bool:
    """Authorize *deleting* an existing chat message.

    Allowed for an admin, for the sender inside their self-action window, and
    for a mentor of this group removing a student's message (AM8). Deliberately
    separate from ``can_manage_chat_message``: a mentor may take a student's
    message down, but may not rewrite it, and restoring stays admin-only.
    """
    if can_manage_chat_message(user, message):
        return True

    target_group = _group_from_value(
        getattr(message, "group", None) or getattr(message, "group_id", None)
    )
    if target_group is None:
        return False

    return (
        _is_group_mentor(user, target_group.id)
        and _was_sent_by_a_student(message, target_group.id)
    )


def can_restore_chat_message(user, message) -> bool:
    """Authorize undoing a removal, and reading back what was removed.

    An admin may reverse anything. A mentor may reverse only their own
    removal, and only while they still mentor that group - the same authority
    that let them take it down, pointed the other way. A member who deleted
    their own message inside the self-action window does not get it back: that
    path has always been one-way, and widening it here would expose text the
    sender chose to withdraw.
    """
    if not user or not getattr(user, "is_authenticated", False) or message is None:
        return False
    if is_admin(user):
        return True
    if getattr(message, "deleted_by_id", None) != getattr(user, "id", None):
        return False

    target_group = _group_from_value(
        getattr(message, "group", None) or getattr(message, "group_id", None)
    )
    return target_group is not None and _is_group_mentor(user, target_group.id)


def can_manage_chat_message(user, message) -> bool:
    """Authorize edit or delete of an existing chat message.

    Allowed iff the caller is an admin, or is the original sender within
    the self-action window — delegated to
    ``Messages.can_be_self_actioned_by`` so the window definition lives
    in one place. Mentor/supervisor roles do not by themselves grant
    moderation rights.
    """
    if not user or not user.is_authenticated or message is None:
        return False

    # Once automated screening has suppressed a message, the linked ticket is
    # the only moderation surface. Neither the sender nor a group-page admin
    # may edit/delete the evidence while support is deciding its outcome.
    if getattr(message, "is_suppressed", False):
        return False

    target_group = _group_from_value(getattr(message, "group", None) or getattr(message, "group_id", None))
    if target_group is None:
        return False

    if is_admin(user):
        return True

    self_action = getattr(message, "can_be_self_actioned_by", None)
    if callable(self_action):
        return bool(self_action(user))
    return False
