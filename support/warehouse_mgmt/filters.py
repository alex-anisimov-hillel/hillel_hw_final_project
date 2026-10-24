import django_filters
from django.db.models import F

from warehouse_mgmt.models import StockItem, StockMovement


class StockItemFilter(django_filters.FilterSet):
    warehouse = django_filters.CharFilter(field_name="warehouse__code")
    low_stock = django_filters.BooleanFilter(method="filter_low_stock")

    class Meta:
        model = StockItem
        fields = ["book_id", "warehouse", "low_stock"]

    def filter_low_stock(self, queryset, name, value):
        low = queryset.filter(quantity__lte=F("reserved") + F("low_stock_threshold"))
        return low if value else queryset.exclude(pk__in=low.values("pk"))


class StockMovementFilter(django_filters.FilterSet):
    book_id = django_filters.NumberFilter(field_name="stock_item__book_id")

    class Meta:
        model = StockMovement
        fields = ["book_id", "kind", "reservation"]
