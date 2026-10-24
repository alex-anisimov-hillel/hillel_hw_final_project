from django.urls import path
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from book_shop.custom_permissions import IsAdminOrReadOnly

from book_shop.urls import router
from books import views as books_views
from books.filters import BookFilter
from books.models import Book
from books.pagination import BookPagination
from books.serializers import BookSerializer


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    pagination_class = BookPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = BookFilter
    permission_classes = [IsAdminOrReadOnly]


router.register(r"books", BookViewSet)

urlpatterns = [
    path("", books_views.BooksListView.as_view(), name="book_list"),
    path("<pk>/", books_views.BookDetailView.as_view(), name="book_detail"),
    path(
        "admin/create/<pk>/", books_views.BookCreateView.as_view(), name="book_create"
    ),
    path("admin/edit/<pk>/", books_views.BookEditView.as_view(), name="book_update"),
    path(
        "admin/delete/<pk>/", books_views.BookDeleteView.as_view(), name="book_delete"
    ),
]
