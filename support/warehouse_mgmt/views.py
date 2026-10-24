"""REST API. Class-based views share behaviour through small base classes:

AuditLogMixin + RequiredPermissionMixin
    ├── PermissionedAPIView ── StockAvailabilityView, BulkAvailabilityView,
    │        └── StockMutationView ── RestockView, AdjustView
    ├── InventoryViewSet ── InventoryReadOnlyViewSet ── StockMovementViewSet
    │        └── ReservationViewSet
    └── ManagedModelViewSet ── WarehouseViewSet, StockItemViewSet
"""

import logging

from django.core.cache import cache
from django.db import connection
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from warehouse_mgmt import services
from warehouse_mgmt.filters import StockItemFilter, StockMovementFilter
from warehouse_mgmt.models import StockItem, StockMovement, StockReservation, Warehouse
from warehouse_mgmt.permissions import (
    HasRequiredPermission,
    IsReservationOwnerOrManager,
    RequiredPermissionMixin,
    StrictModelPermissions,
)
from warehouse_mgmt.serializers import (
    AdjustSerializer,
    AvailabilityListSerializer,
    AvailabilityRequestSerializer,
    AvailabilitySerializer,
    HealthSerializer,
    ReservationCreateSerializer,
    ReservationSerializer,
    RestockSerializer,
    StockItemSerializer,
    StockMovementSerializer,
    WarehouseSerializer,
)

logger = logging.getLogger(__name__)

VIEW_STOCK = "warehouse_mgmt.view_stockitem"
MANAGE_RESERVATION = "warehouse_mgmt.manage_reservation"


class AuditLogMixin:
    """Log method, path, user and resulting status of every API call."""

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        user = getattr(request, "user", None)
        logger.info(
            "%s %s -> %s (user=%s)",
            request.method,
            request.path,
            response.status_code,
            getattr(user, "pk", None) or "anonymous",
        )
        return response


# --------------------------------------------------------------------------- APIViews
class PermissionedAPIView(AuditLogMixin, RequiredPermissionMixin, APIView):
    permission_classes = [HasRequiredPermission]


@extend_schema_view(get=extend_schema(responses=AvailabilitySerializer))
class StockAvailabilityView(PermissionedAPIView):
    """GET /api/stock/<book_id>/ - availability of one book (cached)."""

    required_permission = VIEW_STOCK

    def get(self, request, book_id):
        return Response(services.get_availability([book_id])[book_id])


@extend_schema_view(
    post=extend_schema(
        request=AvailabilityRequestSerializer, responses=AvailabilityListSerializer
    )
)
class BulkAvailabilityView(PermissionedAPIView):
    """POST /api/stock/availability/ {"book_ids": [...]} - many books at once."""

    required_permission = VIEW_STOCK

    def post(self, request):
        serializer = AvailabilityRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        availability = services.get_availability(serializer.validated_data["book_ids"])
        return Response({"items": list(availability.values())})


class StockMutationView(PermissionedAPIView):
    """Template for write endpoints on StockItem: validate, perform, serialize."""

    serializer_class = None
    success_status = status.HTTP_201_CREATED

    def perform(self, data, user):
        raise NotImplementedError

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = self.perform(serializer.validated_data, request.user)
        return Response(StockItemSerializer(item).data, status=self.success_status)


@extend_schema_view(
    post=extend_schema(request=RestockSerializer, responses={201: StockItemSerializer})
)
class RestockView(StockMutationView):
    """POST /api/stock/restock/ - add delivered books to a warehouse."""

    required_permission = "warehouse_mgmt.restock_stockitem"
    serializer_class = RestockSerializer

    def perform(self, data, user):
        return services.restock(
            book_id=data["book_id"],
            quantity=data["quantity"],
            warehouse_code=data.get("warehouse"),
            title=data.get("title", ""),
            isbn=data.get("isbn", ""),
            note=data.get("note", ""),
            user=user,
        )


@extend_schema_view(
    post=extend_schema(request=AdjustSerializer, responses={200: StockItemSerializer})
)
class AdjustView(StockMutationView):
    """POST /api/stock/adjust/ - correct on-hand quantity (+/-), e.g. stocktaking."""

    required_permission = "warehouse_mgmt.adjust_stockitem"
    serializer_class = AdjustSerializer
    success_status = status.HTTP_200_OK

    def perform(self, data, user):
        return services.adjust_stock(
            book_id=data["book_id"],
            delta=data["delta"],
            note=data["note"],
            warehouse_code=data.get("warehouse"),
            user=user,
        )


@extend_schema_view(get=extend_schema(responses=HealthSerializer, auth=[]))
class HealthView(APIView):
    """GET /health/ - unauthenticated liveness + dependency check (DB, cache)."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        checks = {}
        try:
            connection.ensure_connection()
            checks["database"] = True
        except Exception:
            logger.exception("Health check: database unavailable")
            checks["database"] = False
        try:
            cache.set("health:ping", "1", 5)
            checks["cache"] = cache.get("health:ping") == "1"
        except Exception:
            logger.exception("Health check: cache unavailable")
            checks["cache"] = False
        ok = all(checks.values())
        return Response(
            {"status": "ok" if ok else "degraded", **checks},
            status=status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# ------------------------------------------------------------------------- ViewSets
class InventoryViewSet(AuditLogMixin, RequiredPermissionMixin, viewsets.GenericViewSet):
    permission_classes = [HasRequiredPermission]


class InventoryReadOnlyViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, InventoryViewSet
):
    pass


class StockMovementViewSet(InventoryReadOnlyViewSet):
    """Read-only movement ledger."""

    queryset = StockMovement.objects.select_related("stock_item__warehouse")
    serializer_class = StockMovementSerializer
    filterset_class = StockMovementFilter
    required_permission = "warehouse_mgmt.view_stockmovement"


class ReservationViewSet(mixins.CreateModelMixin, InventoryReadOnlyViewSet):
    """Reserve stock for an order, then confirm (paid) or cancel it."""

    queryset = StockReservation.objects.prefetch_related("lines__stock_item__warehouse")
    serializer_class = ReservationSerializer
    permission_classes = [HasRequiredPermission, IsReservationOwnerOrManager]
    filterset_fields = ["status", "order_id"]
    required_permissions = {
        "list": "warehouse_mgmt.view_stockreservation",
        "retrieve": "warehouse_mgmt.view_stockreservation",
        "create": MANAGE_RESERVATION,
        "confirm": MANAGE_RESERVATION,
        "cancel": MANAGE_RESERVATION,
    }

    def get_serializer_class(self):
        if self.action == "create":
            return ReservationCreateSerializer
        return ReservationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        reservation, created = services.reserve_stock(
            order_id=data["order_id"],
            items=[(i["book_id"], i["quantity"]) for i in data["items"]],
            user=request.user,
            ttl_minutes=data.get("ttl_minutes"),
        )
        return Response(
            ReservationSerializer(reservation).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def _transition(self, request, service):
        reservation = self.get_object()  # runs object-level permission check
        updated = service(reservation.pk, user=request.user)
        return Response(ReservationSerializer(updated).data)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        return self._transition(request, services.confirm_reservation)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._transition(request, services.cancel_reservation)


class ManagedModelViewSet(AuditLogMixin, viewsets.ModelViewSet):
    """Standard CRUD protected by Django model permissions (reads included)."""

    permission_classes = [StrictModelPermissions]


class WarehouseViewSet(ManagedModelViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer


class StockItemViewSet(ManagedModelViewSet):
    """Item metadata (title, ISBN, threshold). Quantities change via restock/adjust."""

    queryset = StockItem.objects.select_related("warehouse")
    serializer_class = StockItemSerializer
    filterset_class = StockItemFilter
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
