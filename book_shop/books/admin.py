from django.db.models import Q, Count
from django.contrib import admin
from books.models import Book


# Register your models here.
def checkIfNeedsRefill():
    books = Book.objects.all().filter(stock__lt=10)
    if len(books) > 0:
        print("\nThese books need to be restocked:")
        for book in books:
            print(f"{book.title} -- {book.stock}")
    else:
        print("\nThere is no need to restock any books")


def Q_objectTest():
    specific_books = Book.objects.all().filter(Q(stock__gt=10) | Q(price__gt=20))
    print("\nQ-object result:")
    for book in specific_books:
        print(book.title)
    print("\n")


def AuthorsAndTheirBooks():
    authors = Book.objects.annotate(num_books=Count("author"))
    for author in authors:
        print(f"{author.author} wrote {author.num_books} books")
    print("\n")


class BookAdmin(admin.ModelAdmin):
    search_fields = ["title"]
    list_filter = ["category", "author"]
    list_display = ["title", "author", "category", "stock", "price"]


admin.site.register(Book, BookAdmin)

# ORM EXAMPLES
# checkIfNeedsRefill()
# Q_objectTest()
# AuthorsAndTheirBooks()
