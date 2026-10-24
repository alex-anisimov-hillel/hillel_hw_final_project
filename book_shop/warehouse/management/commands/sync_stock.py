from django.core.management.base import BaseCommand

from warehouse.tasks import sync_stock_levels


class Command(BaseCommand):
    help = "Pull stock levels from the warehouse service into Book.stock (runs inline)."

    def handle(self, *args, **options):
        result = sync_stock_levels.apply().get()
        self.stdout.write(self.style.SUCCESS(f"Stock sync done: {result}"))
