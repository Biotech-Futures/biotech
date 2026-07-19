import uuid

from django.db import IntegrityError, models, transaction
from django.db.models import F, Q
from django.utils import timezone

GROUP_NAME_PREFIX = "BTF_"


class GroupAutoNameUnavailable(Exception):
    """The pk-derived auto name is already held by a hand-named active group."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(
            f'The auto-generated group name "{name}" is already taken by another '
            "group. Rename that group or supply a name explicitly."
        )


def generate_group_name(group_id: int, marker: str = "") -> str:
    """Auto-name for a group, derived from its pk so uniqueness needs no counter.

    ``marker`` tags the group's origin (``"C"`` = co-registered) -> ``BTF_C0042``.
    """
    return f"{GROUP_NAME_PREFIX}{marker}{group_id:04d}"


class GroupQuerySet(models.QuerySet):
    """Canonical scoping primitives for the Groups model.

    Lives at the data-access layer so every consumer (dashboard
    preview, future admin tooling, etc.) shares one source of truth for
    "which groups can this user see". Compose with ``.annotate``,
    ``.prefetch_related``, ``.filter`` etc. downstream.
    """

    def active(self):
        """Exclude soft-deleted groups."""
        return self.filter(deleted_at__isnull=True)

    def for_user(self, user, *, mine=False):
        """Restrict to groups visible to ``user``.

        Scope rules (mirrors the existing dashboard preview semantics):

        - Admin without ``mine`` → all active groups.
        - Admin with ``mine=True`` → only the groups they are an active
          member of.
        - Non-admin user → only the groups they are an active member of.

        The ``GroupMembership`` and admin helpers are imported inside the
        method to avoid a circular import at module load (``Groups`` is
        imported before ``GroupMembership`` in this package's
        ``__init__``).
        """
        from apps.common.rbac import is_admin
        from apps.groups.models import GroupMembership

        qs = self.active()

        if is_admin(user) and not mine:
            return qs

        member_group_ids = GroupMembership.objects.filter(
            user=user,
            left_at__isnull=True,
        ).values_list("group_id", flat=True)
        return qs.filter(id__in=member_group_ids)


class GroupManager(models.Manager.from_queryset(GroupQuerySet)):
    """Default manager for ``Groups`` exposing the ``GroupQuerySet`` API.

    Using ``Manager.from_queryset`` keeps the manager and queryset in
    lockstep so ``Groups.objects.for_user(...)`` and
    ``Groups.objects.filter(...).for_user(...)`` resolve identically.
    """


class Groups(models.Model):
    objects = GroupManager()

    group_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'groups'
        indexes = [
            models.Index(fields=['deleted_at']),
            models.Index(fields=['created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['group_name'],
                condition=Q(deleted_at__isnull=True),
                name='unique_active_group_name'
            ),
            models.CheckConstraint(
                condition=Q(deleted_at__gte=F('created_at')) | Q(deleted_at__isnull=True),
                name='group_deleted_after_created'
            ),
            models.CheckConstraint(
                condition=~Q(group_name__regex=r'^\s*$'),
                name='group_name_not_empty'
            ),
        ]

    def __str__(self):
        return self.group_name

    @classmethod
    def create_auto_named(cls, marker: str = "") -> "Groups":
        """Create a group named ``BTF_<marker><zero-padded pk>``.

        The pk isn't known until after the insert, so seed a collision-proof
        placeholder and rename once.

        Raises:
            GroupAutoNameUnavailable: a hand-named group already holds that slot.
        """
        placeholder = f"{GROUP_NAME_PREFIX}new-{uuid.uuid4().hex}"
        name = None
        try:
            # Insert and rename share one savepoint, so a taken slot rolls the
            # placeholder row back too rather than leaving it as the real name.
            with transaction.atomic():
                group = cls.objects.create(group_name=placeholder)
                name = generate_group_name(group.id, marker)
                group.group_name = name
                group.save(update_fields=["group_name"])
        except IntegrityError as exc:
            raise GroupAutoNameUnavailable(name or placeholder) from exc
        return group

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def restore(self):
        # Recovery is intentionally limited to clearing the tombstone.
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])
