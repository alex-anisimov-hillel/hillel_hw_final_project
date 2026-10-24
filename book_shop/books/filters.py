import django_filters

from .models import Book


class BookFilter(django_filters.FilterSet):
    price_lt = django_filters.NumberFilter(field_name="price", lookup_expr="lt")

    class Meta:
        model = Book
        fields = ["price_lt"]
