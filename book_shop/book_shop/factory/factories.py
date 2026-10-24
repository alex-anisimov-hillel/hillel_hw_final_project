import factory

from books.models import Book
from categories.models import Category
from orders.models import Order
from payment.models import Payment
from users.models import User


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.Sequence(lambda n: f"category-{n}")


class BookFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Book

    title = factory.Faker("sentence", nb_words=3)
    author = factory.Faker("name")
    price = factory.Faker("pydecimal", left_digits=3, right_digits=2, positive=True)
    stock = factory.Faker("random_int", min=0, max=100)
    description = factory.Faker("paragraph")
    category = factory.SubFactory(CategoryFactory)


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.LazyAttribute(
        lambda o: f"{o.first_name}{o.last_name}@example.com".lower()
    )
    first_name = factory.Faker("name")
    last_name = factory.Faker("name")
    phone_number = factory.Faker(
        "pydecimal", left_digits=10, right_digits=0, positive=True
    )
    is_staff = True
    is_active = True


class PaymentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Payment

    id = factory.Sequence(lambda n: n)
    user = factory.SubFactory(UserFactory)
    stripe_payment_intent_id = factory.LazyAttribute(
        lambda o: f"{o.id}stripe_payment_intent_id".lower()
    )
    stripe_charge_id = factory.LazyAttribute(
        lambda o: f"{o.id}stripe_charge_id".lower()
    )
    amount = factory.Faker("random_int", min=0, max=100)
    currency = "USD"
    status = "PENDING"
    description = ""
    metadata = ""
    error = ""
    refund_amount = 0


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order

    user = factory.SubFactory(UserFactory)
    email = factory.SelfAttribute("user.email")
    phone_number = factory.SelfAttribute("user.phone_number")
    address = factory.Faker("address")
    city = factory.Faker("city")
    status = "CREATED"
    total_price = factory.Faker("random_int", min=0, max=100)
    payment_method = factory.SubFactory(PaymentFactory)
