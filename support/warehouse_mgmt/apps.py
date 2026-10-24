from django.apps import AppConfig
from django.db.models.signals import post_migrate


def ensure_groups(sender, **kwargs):
    """Create the role groups and sync their permissions (idempotent).

    Runs after ``migrate`` for this app; ``create_permissions`` (auth) is connected
    earlier, so warehouse_mgmt permissions already exist at this point.
    """
    from django.contrib.auth.models import Group, Permission

    from users.roles import ROLE_PERMISSIONS

    for role, perm_names in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=role)
        perms = []
        for name in perm_names:
            app_label, codename = name.split(".")
            perms.append(
                Permission.objects.get(
                    content_type__app_label=app_label, codename=codename
                )
            )
        group.permissions.set(perms)


class WarehouseMgmtConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "warehouse_mgmt"

    def ready(self):
        post_migrate.connect(ensure_groups, sender=self)
