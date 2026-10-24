BOOK_CACHE_TIMER = 60 * 5


def book_cache_key(pk):
    return f"book:{pk}"
