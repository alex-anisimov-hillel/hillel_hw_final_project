from django.apps import AppConfig


class BooksConfig(AppConfig):
    name = "books"

    def ready(self):
        from books import signals  # noqa: F401
