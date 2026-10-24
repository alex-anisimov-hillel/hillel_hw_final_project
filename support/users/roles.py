"""Group (role) names and the permissions each role gets.

Permissions are Django model permissions plus custom ones declared on the
warehouse_mgmt models. ``warehouse_mgmt.apps.ensure_groups`` applies this table
after every ``migrate`` so groups are always in sync with the code.
"""

WAREHOUSE_MANAGER = "WarehouseManager"
OPERATOR = "Operator"
SERVICE_ACCOUNT = "ServiceAccount"

# role -> list of "app_label.codename"
ROLE_PERMISSIONS = {
    WAREHOUSE_MANAGER: [
        "warehouse_mgmt.view_warehouse",
        "warehouse_mgmt.add_warehouse",
        "warehouse_mgmt.change_warehouse",
        "warehouse_mgmt.delete_warehouse",
        "warehouse_mgmt.view_stockitem",
        "warehouse_mgmt.add_stockitem",
        "warehouse_mgmt.change_stockitem",
        "warehouse_mgmt.restock_stockitem",
        "warehouse_mgmt.adjust_stockitem",
        "warehouse_mgmt.view_stockreservation",
        "warehouse_mgmt.manage_reservation",
        "warehouse_mgmt.view_stockmovement",
    ],
    OPERATOR: [
        "warehouse_mgmt.view_warehouse",
        "warehouse_mgmt.view_stockitem",
        "warehouse_mgmt.restock_stockitem",
        "warehouse_mgmt.view_stockreservation",
        "warehouse_mgmt.view_stockmovement",
    ],
    # The account ProjectA logs in with: read stock, manage reservations, nothing else.
    SERVICE_ACCOUNT: [
        "warehouse_mgmt.view_stockitem",
        "warehouse_mgmt.view_stockreservation",
        "warehouse_mgmt.manage_reservation",
    ],
}
