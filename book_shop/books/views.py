import logging

from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    DeleteView,
    UpdateView,
)
from books.cache_utils import BOOK_CACHE_TIMER, book_cache_key
from books.models import Book

logger = logging.getLogger(__name__)


class LoggingMixin:
    """Log the requested path and response status code for every view using it."""

    def dispatch(self, request, *args, **kwargs):
        logger.info(f"User went to: {request.path}")
        response = super().dispatch(request, *args, **kwargs)
        logger.info("STATUS CODE " + str(response.status_code))

        return response


class BooksListView(LoggingMixin, ListView):
    """List every book, logging each visit via :class:`LoggingMixin`."""

    model = Book
    template_name = "book_list.html"
    context_object_name = "books"


class BookDetailView(DetailView):
    """Show the details of a single book."""

    model = Book
    template_name = "book_detail.html"
    context_object_name = "book"

    def get_object(self, queryset=None):
        pk = self.kwargs[self.pk_url_kwarg]
        key = book_cache_key(pk)

        book = cache.get(key)
        if book is None:
            book = get_object_or_404(Book.objects.select_related("category"), pk=pk)
            cache.set(key, book, BOOK_CACHE_TIMER)
        return book


class BookCreateView(CreateView):
    """Create a new book.

    See ``permission_required``, and AI_REVIEW.md, re: permission enforcement.
    """

    model = Book
    template_name = "book_create.html"
    context_object_name = "book"
    fields = "__all__"
    permission_required = "books.add_book"


class BookDeleteView(DeleteView):
    """Delete a book.

    See ``permission_required``, and AI_REVIEW.md, re: permission enforcement.
    """

    model = Book
    template_name = "book_delete.html"
    context_object_name = "book"
    permission_required = "books.delete_book"


class BookEditView(UpdateView):
    """Edit an existing book.

    See ``permission_required``, and AI_REVIEW.md, re: permission enforcement.
    """

    model = Book
    template_name = "book_update.html"
    context_object_name = "book"
    fields = "__all__"
    permission_required = "books.change_book"
