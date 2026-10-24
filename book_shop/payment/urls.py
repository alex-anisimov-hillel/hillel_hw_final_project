from django.urls import path, include
from payment.views import PaymentViewSet, checkout_view
from orders.views import cart_add, cart_detail, cart_remove, order_create
from book_shop.urls import router

router.register(r"payments", PaymentViewSet, basename="payment")
app_name = "payment"


urlpatterns = [
    path("cart/", cart_detail, name="cart_detail"),
    path("cart/add/<pk>/", cart_add, name="cart_add"),
    path("cart/remove/<pk>/", cart_remove, name="cart_remove"),
    path("order_create/", order_create, name="order_create"),
    path("checkout/<int:order_id>/", checkout_view, name="checkout_order"),
    path("", include(router.urls)),
]
