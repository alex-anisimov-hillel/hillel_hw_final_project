from book_shop.custom_permissions import IsAdminOrReadOnly
from categories.models import Category
from rest_framework import viewsets
from book_shop.urls import router
from categories.serializers import CategorySerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]


router.register(r"categories", CategoryViewSet)

urlpatterns = []
