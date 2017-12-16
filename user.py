import redis

import settings


r = redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)


class CacheUser:
    PREFIX = 'botclient'
    SEP = ':'
    STARTED, BUY_TICKET, ENTER_COUNT, ENTER_TYPE, ENTER_PROMOCODE,  = 0, 1, 2, 3, 4
    ENTER_NAME, START_PAYMENT, SUCCESS, FAIL = 5, 6, 7, 8
    STATUSES = [STARTED, ENTER_COUNT, ENTER_PROMOCODE, START_PAYMENT, SUCCESS, FAIL, ENTER_TYPE, ENTER_NAME, BUY_TICKET]
    STATUS, CHAT_ID, COUNT, PROMO_CODE, NAME = 'status', 'chat_id', 'count', 'promo_code', 'name'
    ID, ENTER_CODE, IS_PROMOTER = 'id', 'enter_code', 'is_promoter'

    def __init__(self, user_id, chat_id):
        self.user_id = str(user_id)
        if not r.exists(self.key):
            r.hset(self.key, self.CHAT_ID, chat_id)
            r.hset(self.key, self.IS_PROMOTER, 0)

    def refresh(self):
        self.flush()
        r.hset(self.key, self.CHAT_ID, self.user_id)
        r.hset(self.key, self.IS_PROMOTER, 0)
        r.hset(self.key, self.STATUS, 0)

    @property
    def key(self):
        return self.SEP.join([self.PREFIX, self.user_id])

    def get(self, field, to_type=None):
        value = r.hget(self.key, str(field))
        if value:
            result = value.decode('utf-8')
            return to_type(result) if to_type else result
        return None

    def set(self, field, value):
        r.hset(self.key, str(field), value)

    def delete(self, field):
        r.hdel(self.key, field)

    def flush(self):
        r.delete(self.key)

    @classmethod
    def get_all(cls):
        for key in r.keys('{}:*'.format(cls.PREFIX)):
            chat_id = key.decode().split('{}:'.format(cls.PREFIX))[1]
            yield cls(chat_id=chat_id, user_id=chat_id)

    @property
    def status(self):
        return self.get(self.STATUS, to_type=int)

    @status.setter
    def status(self, value):
        assert value in self.STATUSES, 'Unsupported status'
        self.set(self.STATUS, value)

    @property
    def chat_id(self):
        return self.get(self.CHAT_ID)

    @property
    def count(self):
        return self.get(self.COUNT, to_type=int)

    @count.setter
    def count(self, value):
        self.set(self.COUNT, value)

    @property
    def promo_code(self):
        return self.get(self.PROMO_CODE)

    @promo_code.setter
    def promo_code(self, value):
        self.set(self.PROMO_CODE, value)

    @property
    def name(self):
        return self.get(self.NAME)

    @name.setter
    def name(self, value):
        self.set(self.NAME, value)

    @property
    def id(self):
        return self.get(self.ID)

    @id.setter
    def id(self, value):
        self.set(self.ID, value)

    @property
    def enter_code(self):
        return self.get(self.ENTER_CODE)

    @enter_code.setter
    def enter_code(self, value):
        self.set(self.ENTER_CODE, value)

    @property
    def is_promoter(self):
        value = self.get(self.IS_PROMOTER)
        if not value:
            return False
        return bool(int(value))

    @is_promoter.setter
    def is_promoter(self, value):
        self.set(self.IS_PROMOTER, value)

