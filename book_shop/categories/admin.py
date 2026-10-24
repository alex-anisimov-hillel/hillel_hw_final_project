from django.contrib import admin

from categories.models import Category
from books.models import Book


class BookInline(admin.TabularInline):
    model = Book
    extra = 0


class CategoryAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    inlines = [BookInline]


# Register your models here.
admin.site.register(Category, CategoryAdmin)
