from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    def create_user(self, email, first_name, last_name, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        if not first_name:
            raise ValueError("Users must have a first name")
        if not last_name:
            raise ValueError("Users must have a last name")
        email = self.normalize_email(email)
        user = self.model(
            email=email, first_name=first_name, last_name=last_name, **extra_fields
        )
        user.set_password(raw_password=password)
        user.save()
        return user

    def create_superuser(self, email, first_name, last_name, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, first_name, last_name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, verbose_name=_("Email"))
    first_name = models.CharField(
        blank=False, max_length=255, verbose_name=_("First Name")
    )
    last_name = models.CharField(
        blank=False, max_length=255, verbose_name=_("Last name")
    )
    phone_number = models.CharField(
        blank=False, max_length=255, unique=True, verbose_name=_("Phone Number")
    )
    is_staff = models.BooleanField(default=False, verbose_name=_("Staff"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name", "phone_number"]

    def __str__(self):
        return f"{self.email} -- {self.first_name} {self.last_name}"

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
