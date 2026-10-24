from rest_framework import serializers
from books.serializers import BookSerializer
from orders.models import Order


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = "__all__"


class CartSerializer(serializers.Serializer):
    book = BookSerializer(read_only=True)
    quantity = serializers.IntegerField(read_only=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
