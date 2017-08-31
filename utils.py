from functools import wraps

from flask import request
from werkzeug.exceptions import Unauthorized
import settings


def check_auth(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization')
        if token != settings.NORMA_BOT_TOKEN:
            raise Unauthorized
        return func()
    return wrapper
