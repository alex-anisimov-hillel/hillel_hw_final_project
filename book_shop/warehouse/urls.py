from django.urls import path

from warehouse.views import WarehouseWebhookView

urlpatterns = [
    path("webhook/", WarehouseWebhookView.as_view(), name="warehouse-webhook"),
]
