# Book Shop

Django-застосунок інтернет-магазину книг з кошиком на сесіях, оформленням
замовлень та оплатою через Stripe.

## Можливості

- Каталог книг з категоріями (django-mptt), CRUD для книг
- Кошик на сесіях (async views) — додавання/видалення позицій, підрахунок суми
- Оформлення замовлення (гостьове або від імені зареєстрованого користувача)
- Оплата через Stripe: створення `PaymentIntent`, підтвердження оплати,
  email-сповіщення про успішну оплату
- Кастомна модель користувача (email як логін)
- Локалізація (django `gettext`)

## Технології

Django 6.1, Django REST Framework, django-mptt, Stripe, PostgreSQL, Redis,
Uvicorn (ASGI), Docker / docker-compose, pytest / pytest-django / pytest-factoryboy.

## Структура репозиторію

```
.
├── Dockerfile              # ОДИН образ для обох проєктів
├── docker-compose.yml      # ОДИН compose: усі сервіси обох проєктів
├── nginx/nginx.conf        # один nginx: :80 → book_shop, :8001 → support
├── .env.example            # шаблон змінних для обох проєктів (реальний .env не комітимо)
├── book_shop/              # ProjectA — книжковий магазин (Django-проєкт `book_shop`)
│   └── warehouse/          #   інтеграція зі складом: клієнт, webhook, Celery-задачі
└── support/                # ProjectB — склад (Django-проєкт `support`, застосунок `warehouse_mgmt`)
```

| Сервіс compose | Проєкт | Призначення |
| --- | --- | --- |
| `web`, `celery`, `celery-beat`, `books_db` | A | магазин (gunicorn, Celery, Postgres) |
| `warehouse-web`, `warehouse-celery`, `warehouse-celery-beat`, `warehouse-db` | B | склад: REST API, резервування, webhook-и |
| `redis` | A + B | один Redis, окремі logical DB (A: 0/1/2, B: 3/4/5) |
| `nginx` | A + B | `:80` → магазин, `:8001` → склад (Swagger: `/api/docs/`) |

Усі app-сервіси запускаються з одного образу; відрізняються лише `working_dir` та
`command`. Внутрішні виклики йдуть Docker-мережею: A → `http://warehouse-web:8000/api`,
B → `http://web:8000/api/warehouse/webhook/` (імена з дефісом, бо Django відхиляє
`Host` з підкресленням).

## Запуск локально (Docker)

1. Скопіюйте/перевірте `.env` (див. `.env.example`: `POSTGRES_*`, `STRIPE_*`,
   `WAREHOUSE_*`). Для складу всі значення мають локальні дефолти в
   `docker-compose.yml`, тож старий `.env` продовжує працювати без змін.
2. Підняти все:
   ```bash
   docker compose up --build
   ```
   Магазин: `http://localhost`, склад: `http://localhost:8001` (UI, `/admin/`,
   `/api/docs/`). Міграції застосовуються автоматично в `entrypoint.sh` обох проєктів.
   Поки `WAREHOUSE_ENABLED=False` (типово), магазин працює як раніше й до складу
   не звертається.

### Увімкнути інтеграцію магазин ↔ склад

```bash
# 1. у .env:  WAREHOUSE_ENABLED=True  (і змініть WAREHOUSE_*_PASSWORD/SECRET)
docker compose up -d --build

# 2. створіть у складі користувача з роллю Operator (або WarehouseManager)
docker compose exec warehouse-web python manage.py createsuperuser
#    у http://localhost:8001/admin/ додайте його в групу Operator

# 3. одноразово перенесіть поточні залишки книг у склад
docker compose exec web python manage.py seed_warehouse --email EMAIL --password PASSWORD
```

Далі: замовлення резервує книги на складі; оплата підтверджує резерв; скасування —
знімає; `Book.stock` у магазині оновлюється webhook-ом зі складу (+ звірка кожні
10 хв, команда `python manage.py sync_stock`). Якщо склад недоступний, замовлення
приймається й резерв повторюється в Celery з backoff.

## Тести та coverage

```bash
pytest
pytest --cov=payment.models --cov=orders.models --cov=users.models --cov-report=term-missing
```

Детальний coverage-звіт (з поясненням, чому саме ці 3 моделі та звідки взяті
цифри) — у `COVERAGE_REPORT.md`.

## AI Usage

У рамках домашнього завдання "Використати AI для покращення проєкту" AI (Claude,
Anthropic) використовувався для трьох задач:

1. **Code review** трьох найскладніших views/serializers проєкту
   (`PaymentViewSet` + `StripePayment`, cart/order views у `orders/views.py`,
   `PaymentSerializer`) — знайдено й виправлено кілька реальних багів (падіння на
   гостьових замовленнях, невідповідність назв полів моделі й серіалізатора,
   втрату `Payment` при переданому `idempotency_key`, відсутню автентифікацію на
   payment-ендпоінтах, мертвий/непрацюючий код у `order_create`). Повний розбір
   "було / рекомендація AI / стало" — у `AI_REVIEW.md`.
2. **Генерація тестів** для моделей `Payment`, `Order`/`OrderItem` та `User` —
   нові тести (позначені коментарем `# Generated with AI, reviewed and modified`)
   цілять саме в раніше непокриту логіку: властивості `is_success`/
   `can_be_refunded`/`remaining_amount`, `OrderItem.get_total()`, і, найважливіше,
   `UserManager.create_user`/`create_superuser` (раніше взагалі не викликались
   жодним тестом, оскільки фабрики `pytest-factoryboy` створюють користувачів в
   обхід менеджера). Детальніше, включно з реальними цифрами покриття "до" (з
   вашого попереднього `.coverage`) — у `COVERAGE_REPORT.md`.
3. **Документація** — docstrings додано до всіх views/viewset-методів проєкту
   (`books/views.py`, `orders/views.py`, `payment/views.py`, `users/views.py`), і
   оновлено цей README.

Повний список промптів, якими виконувалась кожна з трьох задач — у `AI_PROMPTS.md`.

## Налаштування (settings) та змінні оточення

Налаштування розділені на пакет `book_shop/settings/`:

| Модуль | Призначення |
| --- | --- |
| `base.py` | спільні налаштування, усе читається зі змінних оточення |
| `development.py` | `DEBUG=True`, debug-toolbar, e-mail у консоль (типово для `manage.py`, Celery і pytest) |
| `production.py` | `DEBUG=False`, HTTPS-редірект, HSTS, secure/HttpOnly cookies, `X-Frame-Options: DENY`, без debug-toolbar; без `DJANGO_SECRET_KEY`/`DJANGO_ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` (https) застосунок не стартує (типово для `wsgi.py`, `asgi.py` і Docker-образу) |

Активний модуль вибирається змінною `DJANGO_SETTINGS_MODULE`. Секрети беруться з
`.env` (шаблон — `.env.example`; реальний `.env` у git **не комітимо**). Справжні
змінні оточення завжди мають пріоритет над `.env`.

```bash
cp .env.example .env   # заповнити значення
python -c "import secrets; print(secrets.token_urlsafe(60))"   # для DJANGO_SECRET_KEY
python manage.py check --deploy                                   # перевірка production-налаштувань
```

## CI/CD (GitHub Actions)

Pipeline — `.github/workflows/django.yml`:

1. **lint** — `flake8` та `black --check` для `book_shop/` і `support/`
2. **test** — `pytest` + coverage (поріг 70%) для обох проєктів на Postgres і Redis;
   перевірка відсутніх міграцій та `check --deploy` для production-налаштувань
3. **docker** — збірка єдиного образу (контекст — корінь репозиторію), smoke-тест
   обох проєктів, push у Docker Hub (лише `main` і теги `v*`; у pull request образ
   тільки збирається)

Потрібні secrets репозиторію (*Settings → Secrets and variables → Actions*):
`DOCKERHUB_USERNAME` та `DOCKERHUB_TOKEN` (Docker Hub → Account settings →
Personal access tokens, права *Read & Write*). Образ: `<username>/book-shop`.

Локально те саме (для кожного проєкту окремо):

```bash
cd book_shop && pip install -r requirements-dev.txt
flake8 . && black --check . && pytest --cov
cd ../support && flake8 . && black --check . && pytest --cov   # SQLite; з POSTGRES_HOST — Postgres
```
