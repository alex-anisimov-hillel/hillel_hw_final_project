from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from warehouse_mgmt.models import (
    ReservationLine,
    StockItem,
    StockMovement,
    StockReservation,
    Warehouse,
)


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ["id", "name", "code", "address", "is_active", "priority"]


class StockItemSerializer(serializers.ModelSerializer):
    warehouse = serializers.SlugRelatedField(
        slug_field="code", queryset=Warehouse.objects.all()
    )
    available = serializers.IntegerField(read_only=True)

    class Meta:
        model = StockItem
        fields = [
            "id",
            "warehouse",
            "book_id",
            "title",
            "isbn",
            "quantity",
            "reserved",
            "available",
            "low_stock_threshold",
        ]
        # Quantities change only via restock/adjust/reservations (ledger stays true).
        read_only_fields = ["quantity", "reserved"]


class StockMovementSerializer(serializers.ModelSerializer):
    book_id = serializers.IntegerField(source="stock_item.book_id", read_only=True)
    warehouse = serializers.CharField(
        source="stock_item.warehouse.code", read_only=True
    )

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "book_id",
            "warehouse",
            "kind",
            "quantity_delta",
            "reserved_delta",
            "reservation",
            "note",
            "created_at",
        ]


class ReservationLineSerializer(serializers.ModelSerializer):
    warehouse = serializers.CharField(
        source="stock_item.warehouse.code", read_only=True
    )

    class Meta:
        model = ReservationLine
        fields = ["book_id", "quantity", "warehouse"]


class ReservationSerializer(serializers.ModelSerializer):
    lines = ReservationLineSerializer(many=True, read_only=True)

    class Meta:
        model = StockReservation
        fields = ["id", "order_id", "status", "expires_at", "created_at", "lines"]


class ReservationItemInputSerializer(serializers.Serializer):
    book_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=10000)


class ReservationCreateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(min_value=1)
    items = ReservationItemInputSerializer(many=True, allow_empty=False, max_length=100)
    ttl_minutes = serializers.IntegerField(min_value=1, max_value=1440, required=False)


class AvailabilitySerializer(serializers.Serializer):
    """Aggregated stock of one book across all active warehouses."""

    book_id = serializers.IntegerField()
    tracked = serializers.BooleanField(help_text=_("False if the book is unknown."))
    quantity = serializers.IntegerField()
    reserved = serializers.IntegerField()
    available = serializers.IntegerField()
    in_stock = serializers.BooleanField()


class AvailabilityListSerializer(serializers.Serializer):
    items = AvailabilitySerializer(many=True)


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()
    database = serializers.BooleanField()
    cache = serializers.BooleanField()


class AvailabilityRequestSerializer(serializers.Serializer):
    book_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), allow_empty=False, max_length=500
    )


class RestockSerializer(serializers.Serializer):
    book_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=1_000_000)
    warehouse = serializers.SlugField(required=False)
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    isbn = serializers.CharField(max_length=20, required=False, allow_blank=True)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)


class AdjustSerializer(serializers.Serializer):
    book_id = serializers.IntegerField(min_value=1)
    delta = serializers.IntegerField()
    warehouse = serializers.SlugField(required=False)
    note = serializers.CharField(max_length=255)

    def validate_delta(self, value):
        if value == 0:
            raise serializers.ValidationError(_("Delta must not be zero."))
        return value
