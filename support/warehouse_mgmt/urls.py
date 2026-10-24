from django.urls import include, path
from rest_framework.routers import DefaultRouter

from warehouse_mgmt import views

router = DefaultRouter()
router.register("warehouses", views.WarehouseViewSet, basename="warehouse")
router.register("stock-items", views.StockItemViewSet, basename="stockitem")
router.register("movements", views.StockMovementViewSet, basename="movement")
router.register("reservations", views.ReservationViewSet, basename="reservation")

urlpatterns = [
    path(
        "stock/availability/", views.BulkAvailabilityView.as_view(), name="stock-bulk"
    ),
    path("stock/restock/", views.RestockView.as_view(), name="stock-restock"),
    path("stock/adjust/", views.AdjustView.as_view(), name="stock-adjust"),
    path(
        "stock/<int:book_id>/",
        views.StockAvailabilityView.as_view(),
        name="stock-detail",
    ),
    path("", include(router.urls)),
]
