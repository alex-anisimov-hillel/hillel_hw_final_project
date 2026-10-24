from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from warehouse_mgmt.views import HealthView
from warehouse_mgmt.views_ui import ReservationListView, StockDashboardView
from users.views import MeView

urlpatterns = [
    path("", StockDashboardView.as_view(), name="stock-dashboard"),
    path("reservations/", ReservationListView.as_view(), name="reservation-list"),
    path("health/", HealthView.as_view(), name="health"),
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("api/auth/me/", MeView.as_view(), name="me"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="api-docs"
    ),
    path("api/", include("warehouse_mgmt.urls")),
]
