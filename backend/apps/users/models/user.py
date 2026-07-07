from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone

class UserManager(BaseUserManager):
    use_in_migrations = True
    
    def create_user(self, *, email: str, password: str = None, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()
        if password:
            extra.setdefault("account_status", User.AccountStatus.ACTIVE)
        else:
            extra.setdefault("account_status", User.AccountStatus.PENDING)
        extra.setdefault("is_active", extra["account_status"] == User.AccountStatus.ACTIVE)
        user = self.model(
            email=email,
            **extra
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password, **extra):
        if not password:
            raise ValueError("Superusers must have a password")
        extra.setdefault("first_name", "")
        extra.setdefault("last_name", "")
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("account_status", User.AccountStatus.ACTIVE)
        extra.setdefault("is_active", True)
        return self.create_user(email=email, password=password, **extra)

class User(AbstractUser):
    class AccountStatus(models.TextChoices):
        INVITED = "invited", "Invited"
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        DEACTIVATED = "deactivated", "Deactivated"

    username = None
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=255, blank=False)
    last_name  = models.CharField(max_length=255, blank=False)
    state = models.ForeignKey('groups.CountryStates', on_delete=models.PROTECT,
                              null=True, blank=True, related_name='users')
    is_active = models.BooleanField(default=False)
    account_status = models.CharField(
        max_length=50,
        choices=AccountStatus.choices,
        default=AccountStatus.PENDING,
    )
    invited_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=64, default="UTC", blank=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        db_table = "users"
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["state"]),
            models.Index(fields=["account_status"]),
        ]

    # ----- Account status: prefer the explicit methods below -----
    #
    # `is_active` is the boolean Django auth checks; `account_status` is the
    # richer enum the product cares about. Writes should go through the
    # methods (`activate`, `deactivate`, `suspend`, `invite`, `mark_pending`)
    # so the two stay in lock-step and the right timestamp gets stamped.
    #
    # The reconciliation logic in `save()` below is a compatibility shim
    # for legacy callers that still set just one of the two fields. New
    # code must NOT rely on it.

    def activate(self, *, save: bool = True) -> "User":
        self.account_status = self.AccountStatus.ACTIVE
        self.is_active = True
        if self.activated_at is None:
            self.activated_at = timezone.now()
        if save:
            self.save(update_fields=["account_status", "is_active", "activated_at"])
        return self

    def deactivate(self, *, save: bool = True) -> "User":
        self.account_status = self.AccountStatus.DEACTIVATED
        self.is_active = False
        if save:
            self.save(update_fields=["account_status", "is_active"])
        return self

    def suspend(self, *, save: bool = True) -> "User":
        self.account_status = self.AccountStatus.SUSPENDED
        self.is_active = False
        if save:
            self.save(update_fields=["account_status", "is_active"])
        return self

    def invite(self, *, save: bool = True) -> "User":
        self.account_status = self.AccountStatus.INVITED
        self.is_active = False
        if self.invited_at is None:
            self.invited_at = timezone.now()
        if save:
            self.save(update_fields=["account_status", "is_active", "invited_at"])
        return self

    def mark_pending(self, *, save: bool = True) -> "User":
        self.account_status = self.AccountStatus.PENDING
        self.is_active = False
        if save:
            self.save(update_fields=["account_status", "is_active"])
        return self

    def apply_account_status(self, status: "User.AccountStatus", *, save: bool = True) -> "User":
        """Dispatch helper for code paths that receive an enum value directly
        (e.g. a serialized PATCH body). Prefer the named methods when the
        intent is known at the call site."""
        method = {
            self.AccountStatus.ACTIVE: self.activate,
            self.AccountStatus.DEACTIVATED: self.deactivate,
            self.AccountStatus.SUSPENDED: self.suspend,
            self.AccountStatus.INVITED: self.invite,
            self.AccountStatus.PENDING: self.mark_pending,
        }[self.AccountStatus(status)]
        return method(save=save)

    def save(self, *args, **kwargs):
        # Legacy reconciliation: keep `is_active` and `account_status` aligned
        # for callers that still set only one of them. Once every writer has
        # migrated to the explicit methods above, this block can be deleted.
        update_fields = kwargs.get("update_fields")
        inactive_statuses = {
            self.AccountStatus.INVITED,
            self.AccountStatus.PENDING,
            self.AccountStatus.SUSPENDED,
            self.AccountStatus.DEACTIVATED,
        }

        if update_fields is not None:
            update_fields = set(update_fields)
            if "is_active" in update_fields and "account_status" not in update_fields:
                if self.is_active:
                    self.account_status = self.AccountStatus.ACTIVE
                elif self.account_status == self.AccountStatus.ACTIVE:
                    self.account_status = self.AccountStatus.DEACTIVATED
                update_fields.add("account_status")
            elif "account_status" in update_fields and "is_active" not in update_fields:
                self.is_active = self.account_status == self.AccountStatus.ACTIVE
                update_fields.add("is_active")
            elif self.account_status == self.AccountStatus.ACTIVE:
                self.is_active = True
            elif self.account_status in inactive_statuses:
                self.is_active = False
            kwargs["update_fields"] = list(update_fields)
        else:
            if self.account_status == self.AccountStatus.ACTIVE:
                self.is_active = True
            elif self.is_active:
                self.account_status = self.AccountStatus.ACTIVE
            elif self.account_status in inactive_statuses:
                self.is_active = False
            else:
                self.account_status = self.AccountStatus.DEACTIVATED

        super().save(*args, **kwargs)

    def __str__(self):
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.email
