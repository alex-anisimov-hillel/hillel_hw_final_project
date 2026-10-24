from django.conf import settings
from books.models import Book


class Cart:
    def __init__(self, session, cart) -> None:
        self.session = session
        self.cart = cart

    @classmethod
    async def async_create(cls, request):
        session = request.session
        cart = await session.aget(settings.CART_SESSION_ID)
        if not cart:
            cart = {}
            await session.aset(settings.CART_SESSION_ID, cart)
        return cls(session, cart)

    @classmethod
    def create(cls, request):
        session = request.session
        cart = session.get(settings.CART_SESSION_ID)
        if not cart:
            cart = {}
            session[settings.CART_SESSION_ID] = cart
        return cls(session, cart)

    def add_item(self, book: Book, quantity=1, override_quantity=False):
        book_id = str(book.id)
        if book not in self.cart:
            self.cart[book_id] = {"quantity": 0, "price": str(book.price)}

        if quantity <= 0:
            quantity = 1
        if override_quantity:
            self.cart[book_id]["quantity"] = quantity
        else:
            self.cart[book_id]["quantity"] += quantity

        self.save()

    def save(self):
        self.session.modified = True

    def remove(self, book: Book):
        book_id = str(book.id)
        if book_id in self.cart:
            del self.cart[book_id]
            self.save()

    async def async_clear(self):
        await self.session.apop(settings.CART_SESSION_ID, None)

    def clear(self):
        del self.session[settings.CART_SESSION_ID]

    def __iter__(self):
        books_ids = self.cart.keys()
        books = Book.objects.filter(id__in=books_ids)
        for book in books:
            self.cart[str(book.id)]["book"] = book
        for item in self.cart.values():
            item["total_price"] = float(item["price"]) * int(item["quantity"])
            yield item

    async def async_iter(self):
        books = Book.objects.filter(id__in=self.cart.keys())
        async for book in books:
            self.cart[str(book.id)]["book"] = book
        for item in self.cart.values():
            item["total_price"] = float(item["price"]) * int(item["quantity"])
            yield item

    def get_total(self):
        return sum(
            float(item["price"]) * int(item["quantity"]) for item in self.cart.values()
        )
