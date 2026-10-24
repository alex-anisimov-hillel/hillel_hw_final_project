from django.apps import AppConfig


class WarehouseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "warehouse"

    def ready(self):
        from warehouse import signals  # noqa: F401
        from warehouse.request_id import connect_celery_signals

        connect_celery_signals()
