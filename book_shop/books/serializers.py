from rest_framework import serializers
from books.models import Book
from categories.models import Category
from categories.serializers import CategorySerializer


class BookSerializer(serializers.ModelSerializer):
    category = CategorySerializer()

    class Meta:
        model = Book
        fields = ["title", "stock", "price", "category"]

    def create(self, validated_data):
        category_data = validated_data.pop("category")
        category, _ = Category.objects.get_or_create(**category_data)
        return Book.objects.create(category=category, **validated_data)
