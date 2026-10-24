"""Settings package.

Pick the active settings module with the ``DJANGO_SETTINGS_MODULE`` env var:

* ``book_shop.settings.development`` - local work (default for ``manage.py``)
* ``book_shop.settings.production``  - deployed environments (default for
  ``wsgi.py`` / ``asgi.py`` and the Docker image)
"""
