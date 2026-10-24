from rest_framework.permissions import (
    SAFE_METHODS,
    BasePermission,
    DjangoModelPermissions,
)


class RequiredPermissionMixin:
    """Lets a view declare which Django permission each action needs.

    ``required_permissions`` maps a viewset action (or lowercase HTTP method for plain
    APIViews) to a permission string; ``required_permission`` is the fallback.
    """

    required_permission = None
    required_permissions = {}

    def get_required_permission(self, request):
        key = getattr(self, "action", None) or request.method.lower()
        return self.required_permissions.get(key, self.required_permission)


class HasRequiredPermission(BasePermission):
    """Role check: the user's groups/permissions must include the view's permission."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        perm = view.get_required_permission(request)
        return perm is None or user.has_perm(perm)


class StrictModelPermissions(DjangoModelPermissions):
    """DjangoModelPermissions that also protects reads (GET needs ``view_<model>``)."""

    perms_map = {
        **DjangoModelPermissions.perms_map,
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": ["%(app_label)s.view_%(model_name)s"],
        "HEAD": ["%(app_label)s.view_%(model_name)s"],
    }


class IsReservationOwnerOrManager(BasePermission):
    """Object-level rule: only the creator (e.g. ProjectA's service account) or a
    manager may confirm/cancel a reservation. Reading follows the role permission."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return (
            obj.created_by_id == user.id
            or user.is_superuser
            or user.has_perm("warehouse_mgmt.change_stockitem")  # WarehouseManager only
        )
