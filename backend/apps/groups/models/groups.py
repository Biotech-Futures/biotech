from django.db import models
from django.db.models import F, Q
from django.utils import timezone


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

        - Operational admin without ``mine`` → all active groups within
          their admin track scope (or all active groups if the admin is
          globally scoped via ``is_staff`` / ``is_superuser`` /
          ``AdminScope.is_global``).
        - Operational admin with ``mine=True`` → only the groups they
          are an active member of.
        - Non-admin user → only the groups they are an active member of.

        The ``GroupMembership`` and admin-scope helpers are imported
        inside the method to avoid a circular import at module load
        (``Groups`` is imported before ``GroupMembership`` in this
        package's ``__init__``).
        """
        from apps.groups.models import GroupMembership
        from apps.users.utils.admin_scope import (
            get_admin_track_ids,
            is_operational_admin,
        )

        qs = self.active()

        if is_operational_admin(user) and not mine:
            admin_track_ids = get_admin_track_ids(user)
            if admin_track_ids is None:
                # Globally-scoped admin — no track filter needed.
                return qs
            return qs.filter(track_id__in=admin_track_ids)

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
    track = models.ForeignKey('Tracks', on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'groups'
        indexes = [
            models.Index(fields=['track']),
            models.Index(fields=['deleted_at']),
            models.Index(fields=['created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['track', 'group_name'],
                condition=Q(deleted_at__isnull=True),
                name='unique_active_group_name_per_track'
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

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def restore(self):
        # Recovery is intentionally limited to clearing the tombstone.
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])
