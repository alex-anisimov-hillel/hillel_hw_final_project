"""Small Bootstrap dashboard for warehouse staff (login + permission checked)."""

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.views.generic import ListView

from warehouse_mgmt.models import StockItem, StockReservation


class StaffPageMixin(LoginRequiredMixin, PermissionRequiredMixin):
    paginate_by = 25
    raise_exception = False


class StockDashboardView(StaffPageMixin, ListView):
    model = StockItem
    template_name = "warehouse_mgmt/stock_list.html"
    context_object_name = "items"
    permission_required = "warehouse_mgmt.view_stockitem"

    def get_queryset(self):
        qs = StockItem.objects.select_related("warehouse")
        q = self.request.GET.get("q", "").strip()
        if q:
            query = Q(title__icontains=q) | Q(isbn__icontains=q)
            if q.isdigit():
                query |= Q(book_id=int(q))
            qs = qs.filter(query)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        return context


class ReservationListView(StaffPageMixin, ListView):
    model = StockReservation
    template_name = "warehouse_mgmt/reservation_list.html"
    context_object_name = "reservations"
    permission_required = "warehouse_mgmt.view_stockreservation"

    def get_queryset(self):
        qs = StockReservation.objects.prefetch_related("lines")
        status = self.request.GET.get("status")
        return qs.filter(status=status) if status else qs
