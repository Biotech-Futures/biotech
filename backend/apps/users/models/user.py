from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

class UserManager(BaseUserManager):
    use_in_migrations = True
    
    def create_user(self, *, email: str, password: str = None, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()
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
        return self.create_user(email=email, password=password, **extra)

class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=255, blank=False)
    last_name  = models.CharField(max_length=255, blank=False)
    track = models.ForeignKey('groups.Tracks', on_delete=models.PROTECT,
                              null=True, blank=True, related_name='users')
    state = models.ForeignKey('groups.CountryStates', on_delete=models.PROTECT,
                              null=True, blank=True, related_name='users')
    status = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        db_table = "users"
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["track"]),
            models.Index(fields=["state"]),
        ]

    def __str__(self):
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.email
