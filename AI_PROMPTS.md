# AI_PROMPTS.md

Список промптів, які використовувались для покращення проєкту "Книжковий магазин"
за допомогою AI (Claude, Anthropic). Кожен блок відповідає одному з трьох
обов'язкових пунктів завдання.

## 1. Code Review

**Промпт 1 — PaymentViewSet + StripePayment:**
> Ось мій Django REST Framework ViewSet для платежів через Stripe
> (`payment/views.py`, метод `create_payment_intent` та `confirm_payment`) і сервіс
> `payment/stripe_service.py`, який він викликає. Проведи детальний code review:
> перевір на логічні баги, edge cases (гостьові користувачі, відсутні поля),
> проблеми безпеки (доступ анонімних користувачів) та відповідність назв полів
> реальній моделі `Payment`. Для кожної знахідки поясни, чому це проблема, і
> запропонуй конкретне виправлення коду.

**Промпт 2 — orders/views.py:**
> Проаналізуй `orders/views.py` (async views `cart_add`, `cart_detail`, `cart_remove`,
> `order_create`) на логічні помилки, мертвий/недосяжний код, "голі" `except`, незапущені
> корутини (`await` там, де він відсутній) і валідацію користувацького вводу.

**Промпт 3 — PaymentSerializer:**
> Порівняй поля серіалізатора `PaymentSerializer` (`payment/serializers.py`) з реальними
> полями і властивостями моделі `Payment` (`payment/models.py`). Чи всі оголошені
> read-only поля дійсно існують на моделі? Що станеться при спробі серіалізувати
> реальний об'єкт `Payment`?

**Промпт 4 (додатково, для контексту, не входить в основні 3 пункти):**
> Пробіжись поверхнево і по решті views проєкту (`books/views.py`, `users/views.py`) —
> чи є там очевидні розбіжності між тим, що клас декларує (наприклад, `permission_required`),
> і тим, що клас реально успадковує/виконує?

## 2. Генерація тестів

**Промпт 5 — Payment:**
> Згенеруй pytest-тести для моделі `Payment` (`payment/models.py`), використовуючи
> наявні pytest-factoryboy фікстури (`payment_factory`) з `conftest.py`/`factories.py`.
> Особливо покрий властивості `is_success`, `can_be_refunded` (усі гілки: успішний
> платіж, неуспішний платіж, повністю повернутий платіж) і `remaining_amount`.

**Промпт 6 — Order / OrderItem:**
> Згенеруй тести для моделей `Order` та `OrderItem` (`orders/models.py`): метод
> `OrderItem.get_total()`, `__str__` обох моделей, і сценарій гостьового замовлення
> (`Order` без `user`, оскільки поле `null=True, blank=True`).

**Промпт 7 — User / UserManager:**
> Згенеруй тести для `UserManager.create_user` і `create_superuser`
> (`users/models.py`), включно з усіма `ValueError`, які мають виникати при
> відсутньому `email`/`first_name`/`last_name` для `create_user`, і при
> `is_staff=False`/`is_superuser=False` для `create_superuser`. Перевір також, що
> пароль зберігається хешованим (`check_password`).

Кожен згенерований тест позначений коментарем `# Generated with AI, reviewed and modified` —
перед додаванням у проєкт тести переглянуті вручну: перевірені назви фікстур
(`payment_factory`, `order_factory`, `book_factory`, `user_factory` — вже наявні в
`conftest.py`), значення полів (`Decimal`, значення `TextChoices`) і те, що жоден тест
не покладається на порядок виконання інших тестів.

## 3. Документація

**Промпт 8 — Docstrings:**
> Додай docstring до кожного view-класу/функції та кожного методу-екшена в
> `books/views.py`, `orders/views.py`, `payment/views.py`, `users/views.py`. Коротко
> опиши призначення, важливі побічні ефекти (email, зміна сесії/кошика) і граничні
> випадки (гостьовий користувач, відсутній об'єкт).

**Промпт 9 — README:**
> Онови `README.md` проєкту `book_shop`: додай короткий опис проєкту (Django-магазин
> книг зі Stripe-платежами), як його запустити локально (docker-compose, `.env`,
> міграції), команду для тестів і покриття, і додай секцію "AI Usage" з коротким
> описом того, для чого використовувався AI, і посиланням на `AI_REVIEW.md` та
> `AI_PROMPTS.md`.
