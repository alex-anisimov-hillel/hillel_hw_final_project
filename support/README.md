# ProjectB — warehouse service (`support/`)

Складський сервіс до книжкового магазину (`../book_shop`): залишки, резервування під
замовлення, журнал рухів. Django-проєкт `support`, основний застосунок `warehouse_mgmt`,
Custom User у `users`. Спілкується з ProjectA **лише через REST API (JWT)** та
підписані webhook-и. Запускається разом з магазином єдиним `docker-compose.yml`
у корені репозиторію (див. кореневий `README.md`).

**Стек:** Django 6.1 · DRF · SimpleJWT · PostgreSQL · Redis · Celery (+beat) · NGINX · Gunicorn.
**З вимог:** Custom User (email) · групи/permissions · CBV з наслідуванням · JWT ·
Celery tasks · i18n (en/uk) · кешування (Redis) · Bootstrap UI · logging з `X-Request-ID`.

```
ProjectA (book_shop)                         ProjectB (support)
  order_create ───── JWT, X-Request-ID ────► POST /api/reservations/        (ідемпотентно по order_id)
  Order PAID ──────────────────────────────► POST /api/reservations/{id}/confirm/
  Order CANCELED ──────────────────────────► POST /api/reservations/{id}/cancel/
  Celery (sync) ───────────────────────────► POST /api/stock/availability/
  POST /api/warehouse/webhook/ ◄──── HMAC ─── stock.changed / stock.low
```

Спільний ключ — `book_id` (pk книги в ProjectA).

## Доступ

| Що | URL (локально) |
| --- | --- |
| Дашборд (Bootstrap, en/uk) | http://localhost:8001/ |
| Admin | http://localhost:8001/admin/ |
| Swagger | http://localhost:8001/api/docs/ |
| Health | http://localhost:8001/health/ |

## Ролі (groups)

| Група | Можливості |
|---|---|
| `WarehouseManager` | усе: склади, позиції, поповнення, коригування, резервування |
| `Operator` | перегляд, поповнення (`restock`) |
| `ServiceAccount` | перегляд залишків + резервування/підтвердження/скасування (для ProjectA) |

Групи й права синхронізуються після кожного `migrate` (`warehouse_mgmt/apps.py`,
таблиця — `users/roles.py`). Object-level правило: підтвердити/скасувати резерв може
лише його автор (сервісний акаунт) або менеджер. Сервісний акаунт для ProjectA
створюється при старті з `WAREHOUSE_SERVICE_EMAIL/PASSWORD`.

## API

| Метод | URL | Хто | Опис |
|---|---|---|---|
| POST | `/api/auth/token/`, `/refresh/`, `/verify/` | усі | JWT (у токені claim `groups`) |
| GET | `/api/auth/me/` | авторизовані | email, групи, права |
| GET | `/api/stock/{book_id}/` | view_stockitem | залишок (кеш Redis, 60 с) |
| POST | `/api/stock/availability/` | view_stockitem | залишки списку книг |
| POST | `/api/reservations/` | manage_reservation | `{order_id, items:[{book_id, quantity}]}` → 201 / 200 (повтор) / 409 |
| POST | `/api/reservations/{id}/confirm/` · `/cancel/` | власник або менеджер | завершити / скасувати |
| POST | `/api/stock/restock/` · `/adjust/` | Operator+ / Manager | поповнення / коригування |
| CRUD | `/api/warehouses/`, `/api/stock-items/`, GET `/api/movements/` | model permissions | |

Помилки мають єдиний формат `{"detail", "code", "request_id"}`; `Accept-Language: uk`
повертає українські повідомлення. Нестача товару — `409` з `shortages`.

## Celery

- `expire_stale_reservations` (щохвилини) — знімає прострочені резерви (TTL 30 хв);
- `check_low_stock` (кожні 30 хв) — лог + webhook `stock.low`;
- `generate_stock_report` (щодня 02:00) — CSV у `reports/`;
- `notify_stock_changed` / `send_webhook` — після кожної зміни залишку
  (`transaction.on_commit`), retry з backoff.

## Надійність

- `select_for_update` у фіксованому порядку, резерв ідемпотентний по `order_id` →
  немає перепродажу й дублів при ретраях (перевірено паралельними тестами на PostgreSQL);
- `X-Request-ID` проходить A → B → webhook → A і видно в усіх логах (`[request_id]`);
- webhook: HMAC-SHA256(`timestamp.body`) + перевірка свіжості + дедуплікація по id події.

## Налаштування

`support/settings/{base,development,production,test}.py`; змінні та їх дефолти для
Docker — у `docker-compose.yml` (блок `x-warehouse-env`) і `.env.example`
(секція `WAREHOUSE_*`). Production вимагає `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`
(без `*`, з `warehouse-web`), `CSRF_TRUSTED_ORIGINS` (https) і `WEBHOOK_SECRET`.

## Тести

```bash
cd support
pytest                          # SQLite, без зовнішніх сервісів (3 тести конкурентності пропускаються)
POSTGRES_HOST=localhost POSTGRES_USER=... POSTGRES_PASSWORD=... pytest   # PostgreSQL, повний набір
```
