"""One-off bootstrap: copy the shop's current Book.stock into the warehouse service.

Only books the warehouse does not track yet are pushed, so the command is safe to
re-run. Needs credentials of a warehouse Operator/Manager (the service account may not
restock): pass --email/--password or WAREHOUSE_ADMIN_EMAIL/WAREHOUSE_ADMIN_PASSWORD.
"""

import os

from django.core.management.base import BaseCommand, CommandError

from books.models import Book
from warehouse.client import WarehouseClient
from warehouse.exceptions import WarehouseError


class Command(BaseCommand):
    help = "Seed the warehouse service with the current Book.stock values."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=os.getenv("WAREHOUSE_ADMIN_EMAIL", ""))
        parser.add_argument(
            "--password", default=os.getenv("WAREHOUSE_ADMIN_PASSWORD", "")
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, email, password, dry_run, **options):
        if not email or not password:
            raise CommandError(
                "Provide --email and --password of a warehouse Operator/Manager."
            )
        client = WarehouseClient(email=email, password=password, max_attempts=3)
        books = list(Book.objects.all())
        pushed = 0
        try:
            for start in range(0, len(books), 200):
                chunk = books[start : start + 200]
                tracked = client.get_availability([b.pk for b in chunk])
                for book in chunk:
                    if tracked[book.pk]["tracked"] or book.stock <= 0:
                        continue
                    self.stdout.write(f"{book.pk}: {book.title} -> {book.stock}")
                    if not dry_run:
                        client.restock(
                            book.pk, book.stock, title=book.title, note="initial seed"
                        )
                    pushed += 1
        except WarehouseError as exc:
            raise CommandError(f"Warehouse error: {exc}") from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Would seed' if dry_run else 'Seeded'} {pushed} book(s)."
            )
        )
