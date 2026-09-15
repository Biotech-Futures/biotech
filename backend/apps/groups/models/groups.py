from django.db import models, transaction
from django.db.models import Case, CharField, F, Max, Q, Value, When
from django.db.models.functions import Concat, Length, LPad, Substr
from django.utils import timezone

GROUP_NAME_PREFIX = "BTF"
AUTO_NAME_REGEX = r"^BTF[0-9]+$"

# Ordering-only pad width; LPad truncates past it, so this bounds display order, not numbering.
_AUTO_NAME_PAD = 12


class GroupAutoNameUnavailable(Exception):
    """The next auto name lost the race to a concurrent create on every attempt."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(
            f'Could not reserve an auto-generated group name (last tried "{name}") '
            "because other groups were being created at the same time. Try again, "
            "or supply a name explicitly."
        )


class GroupAutoNameState(models.Model):
    """Legacy singleton counter. Allocation now follows active ``BTF<n>`` names."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    next_number = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "group_auto_name_state"


def generate_group_name(number: int) -> str:
    """Auto-name for a group -> ``BTF07``."""
    return f"{GROUP_NAME_PREFIX}{number:02d}"


def _highest_active_plus_one() -> int:
    """One past the highest *active* ``BTF<n>``. Empty board starts at 1 (``BTF01``)."""
    auto_names = Groups.objects.filter(
        deleted_at__isnull=True,
        group_name__regex=AUTO_NAME_REGEX,
    ).annotate(
        digits=Substr("group_name", len(GROUP_NAME_PREFIX) + 1)
    )
    width = auto_names.aggregate(width=Max(Length("digits")))["width"]
    if not width:
        return 1

    highest = auto_names.aggregate(
        highest=Max(LPad("digits", width, Value("0")))
    )["highest"]
    return int(highest) + 1


def next_group_number() -> int:
    """Preview the next auto-name number without consuming it.

    Only live groups count. Deleting the last group resets to ``BTF01``.
    Deleting an interior group (e.g. BTF02 while BTF01 and BTF03 remain) still
    yields one past the highest remaining number, so that gap is not refilled.
    """
    return _highest_active_plus_one()


def allocate_group_number() -> int:
    """Reserve and return the next ``BTF<n>`` number."""
    return _highest_active_plus_one()


def group_name_sort_key(field: str = "group_name"):
    """Ordering expression that zero-pads auto-names at query time.

    Without it ``BTF10`` sorts before ``BTF9`` as text. String ops only —
    casting to int would blow up on a hand-named group under Postgres.
    ``field`` accepts a related path so joins can reuse the same key.

    Usage: ``.annotate(group_name_key=group_name_sort_key()).order_by("group_name_key", "id")``
    """
    return Case(
        When(
            **{f"{field}__regex": AUTO_NAME_REGEX},
            then=Concat(
                Value(GROUP_NAME_PREFIX),
                LPad(
                    Substr(field, len(GROUP_NAME_PREFIX) + 1),
                    _AUTO_NAME_PAD,
                    Value("0"),
                ),
            ),
        ),
        default=F(field),
        output_field=CharField(),
    )


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
            models.Index(fields=['group_name'], name='groups_group_name_idx'),
        ]
        constraints = [
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
    def create_auto_named(cls) -> "Groups":
        """Create a group named ``BTF<n>``, the next number in the single series.

        The allocated number comes from active groups only, so deleting the last
        group resets the series to ``BTF01``. Duplicate display names are
        allowed; ``id`` is the unique identifier.
        """
        with transaction.atomic():
            return cls.objects.create(group_name=generate_group_name(allocate_group_number()))

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def restore(self):
        # Recovery is intentionally limited to clearing the tombstone.
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])
