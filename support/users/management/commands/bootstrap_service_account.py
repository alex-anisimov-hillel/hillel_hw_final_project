"""Create/update the ServiceAccount user ProjectA authenticates with.

Reads SERVICE_ACCOUNT_EMAIL / SERVICE_ACCOUNT_PASSWORD (or --email/--password) and is
idempotent, so it is safe to run from the container entrypoint on every start.
"""

import os

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from users.models import User
from users.roles import SERVICE_ACCOUNT


class Command(BaseCommand):
    help = "Create or update the service account used by ProjectA."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=os.getenv("SERVICE_ACCOUNT_EMAIL", ""))
        parser.add_argument(
            "--password", default=os.getenv("SERVICE_ACCOUNT_PASSWORD", "")
        )

    def handle(self, *args, email, password, **options):
        if not email or not password:
            self.stdout.write("SERVICE_ACCOUNT_EMAIL/PASSWORD not set - skipping.")
            return
        try:
            group = Group.objects.get(name=SERVICE_ACCOUNT)
        except Group.DoesNotExist as exc:
            raise CommandError("Group missing - run `migrate` first.") from exc
        user, created = User.objects.get_or_create(
            email=email.lower(),
            defaults={"first_name": "ProjectA", "last_name": "Service"},
        )
        user.set_password(password)
        user.is_active = True
        user.save()
        user.groups.add(group)
        self.stdout.write(
            f"Service account {user.email} {'created' if created else 'updated'}."
        )
