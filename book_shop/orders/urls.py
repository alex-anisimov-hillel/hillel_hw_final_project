from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response


from orders.cart.cart import Cart
from orders.models import Order
from rest_framework import viewsets
from book_shop.urls import router
from orders.serializers import OrderSerializer, CartSerializer


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAdminUser]


class CartViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def _serialize_cart(self, cart):
        return {
            "items": CartSerializer(list(cart), many=True).data,
            "total_price": cart.get_total(),
        }

    def list(self, request):
        cart = Cart.create(request)
        return Response(self._serialize_cart(cart))


router.register(r"orders", OrderViewSet)
router.register(r"cart", CartViewSet, basename="cart")

urlpatterns = []
