# One image for the whole repo: book_shop (ProjectA) and support (ProjectB, the
# warehouse service). docker-compose runs every app service from this image and only
# changes the working directory / command, so there is a single Dockerfile to maintain.
FROM python:3.14.7-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=book_shop.settings.production

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    vim \
    libpq-dev \
    python3-dev \
    pkg-config \
    pgloader \
    gcc \
    gettext \
    && rm -rf /var/lib/apt/lists/*

# Both projects share one dependency set (ProjectB needs nothing ProjectA lacks).
COPY book_shop/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the whole repo content (the .dockerignore keeps .env, .venv, caches out).
COPY ./book_shop/ ./book_shop
COPY ./support/ ./support

# ProjectB ships its Ukrainian translation as .po; make sure the .mo is built.
RUN cd support && find locale -name '*.po' -execdir msgfmt django.po -o django.mo \;

EXPOSE 8000

# Default = ProjectA. ProjectB services override working_dir and command in compose.
WORKDIR /app/book_shop
CMD ["gunicorn", "book_shop.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-", "--error-logfile", "-"]
