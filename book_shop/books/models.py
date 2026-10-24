from django.db import models
from categories.models import Category
from django.utils.translation import gettext_lazy as _


class Book(models.Model):
    title = models.CharField(max_length=200, verbose_name=_("Book Title"))
    author = models.CharField(max_length=150, verbose_name=_("Author"))
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, verbose_name=_("Book Category")
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Price")
    )
    description = models.TextField(verbose_name=_("Description"), blank=True, null=True)
    stock = models.PositiveIntegerField(default=0, verbose_name=_("Stock"))

    def __str__(self) -> str:
        return f"{self.title} ({self.author})"

    class Meta:
        verbose_name = _("Book")
        verbose_name_plural = _("Books")
