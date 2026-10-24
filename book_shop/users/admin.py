from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField

from users.models import User


class UserCreationForm(forms.ModelForm):
    pwd1 = forms.CharField(widget=forms.PasswordInput, label="Password")
    pwd2 = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")

    class Meta:
        model = User
        fields = ("email", "phone_number", "first_name", "last_name")

    def clean_password2nd(self):
        password1 = self.cleaned_data.get("pwd1")
        password2 = self.cleaned_data.get("pwd2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["pwd1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField()

    class Meta:
        model = User
        fields = (
            "email",
            "password",
            "first_name",
            "last_name",
            "phone_number",
            "is_active",
            "is_staff",
        )

    def clean_password(self):
        return self.initial["password"]


class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm

    list_display = ("email", "is_active", "is_staff")
    list_filter = ("is_staff",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        ("Type", {"fields": ("is_staff", "is_active")}),
        ("Permissions", {"fields": ("user_permissions",)}),
        ("Groups", {"fields": ("groups",)}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "phone_number",
                    "pwd1",
                    "pwd2",
                ),
            },
        ),
    )
    search_fields = ("email",)
    ordering = ("email",)


admin.site.register(User, UserAdmin)
# admin.site.register(User)
