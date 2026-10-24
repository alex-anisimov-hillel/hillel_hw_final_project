from django.db import models
from django.utils.translation import gettext_lazy as _

# Create your models here.


class Category(models.Model):
    name = models.CharField(max_length=200, verbose_name=_("Category Name"))
    slug = models.SlugField(max_length=200, verbose_name=_("Category Slug"))

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = _("Categories")
