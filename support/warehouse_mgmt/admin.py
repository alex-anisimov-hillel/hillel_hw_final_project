from django.contrib import admin

from warehouse_mgmt.models import (
    ReservationLine,
    StockItem,
    StockMovement,
    StockReservation,
    Warehouse,
)


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "priority", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["code", "name"]


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = [
        "book_id",
        "title",
        "warehouse",
        "quantity",
        "reserved",
        "available",
    ]
    list_filter = ["warehouse"]
    search_fields = ["title", "isbn", "book_id"]
    # Quantities are changed through the API/services so the movement ledger stays true.
    readonly_fields = ["quantity", "reserved"]


class ReservationLineInline(admin.TabularInline):
    model = ReservationLine
    extra = 0
    readonly_fields = ["stock_item", "book_id", "quantity"]
    can_delete = False


@admin.register(StockReservation)
class StockReservationAdmin(admin.ModelAdmin):
    list_display = ["order_id", "status", "expires_at", "created_at"]
    list_filter = ["status"]
    search_fields = ["order_id"]
    inlines = [ReservationLineInline]
    readonly_fields = ["order_id", "status", "expires_at", "created_by"]


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "stock_item",
        "kind",
        "quantity_delta",
        "reserved_delta",
        "note",
    ]
    list_filter = ["kind"]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False
