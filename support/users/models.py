from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, first_name="", last_name="", password=None, **extra):
        if not email:
            raise ValueError("Users must have an email address")
        user = self.model(
            email=self.normalize_email(email),
            first_name=first_name,
            last_name=last_name,
            **extra,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, email, first_name="", last_name="", password=None, **extra
    ):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if extra["is_staff"] is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra["is_superuser"] is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, first_name, last_name, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Email-based custom user. Roles are Django groups (see ``users.roles``)."""

    email = models.EmailField(unique=True, verbose_name=_("Email"))
    first_name = models.CharField(
        max_length=150, blank=True, verbose_name=_("First name")
    )
    last_name = models.CharField(
        max_length=150, blank=True, verbose_name=_("Last name")
    )
    is_staff = models.BooleanField(default=False, verbose_name=_("Staff"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name=_("Date joined"))

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email
