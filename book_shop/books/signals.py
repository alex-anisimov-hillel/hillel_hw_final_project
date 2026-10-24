from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from books.cache_utils import book_cache_key
from books.models import Book


@receiver([post_save, post_delete], sender=Book)
def invalidate_book_cache(sender, instance, **kwargs):
    cache.delete(book_cache_key(instance.pk))
    cache.delete(make_template_fragment_key("book_details", [instance.pk]))
