
class PickyEater:

    def __init__(self, like_func, consume_func):
        self.like_func = like_func
        self.consume_func = consume_func

    def likes(self, cookie):
        return self.like_func(cookie)

    def consume(self, cookie):
        return self.consume_func(cookie)

    def consume_if_is_good(self, cookie):
        if self.likes(cookie):
            self.consume(cookie)
            return True
        else:
            return False


def bulk_consume(picky_eaters, cookie):
    return [plp.consume_if_is_good(cookie) for plp in picky_eaters]
