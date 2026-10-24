from django.contrib import admin

from orders.models import Order, OrderItem


# Register your models here.
class OrderItemInline(admin.StackedInline):
    model = OrderItem


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = ["id", "user", "status", "total_price", "reservation_status"]
    list_filter = ["status", "reservation_status"]
    readonly_fields = ["reservation_id"]


# admin.site.register(Order)
# admin.site.register(OrderItem)
