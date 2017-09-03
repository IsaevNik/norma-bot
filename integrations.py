import json
import logging
import requests

import settings


class NormaApiError(Exception):
    def __init__(self, detail='', *args, **kwargs):
        self.detail = detail


class BadRequestError(NormaApiError):
    pass


class NormaApi:
    CHECK_PROMO_URL, CREATE_GUEST_URL, CREATE_ORDER_URL = 'checkPromoURL', 'createGuestUrl', 'createOrderUrl'
    ACTIVATE_PROMOTER_URL, CREATE_PROMOCODE_URL, GET_STATISTIC_URL = 'activatePromoterURL', 'createCodeUrl', 'getStatisticUrl'

    METHODS = {
        CHECK_PROMO_URL: 'web/check-promo-code/',
        CREATE_GUEST_URL: 'web/guests/',
        CREATE_ORDER_URL: 'web/orders/',
        ACTIVATE_PROMOTER_URL: 'web/promoters/{}/',
        CREATE_PROMOCODE_URL: 'web/promo-codes/',
        GET_STATISTIC_URL: 'web/promoters/{}/statistic/'
    }

    GET, POST, PUT = 'get', 'post', 'put'

    def __init__(self):
        self.back_url = settings.BACKEND
        self.token = settings.BACKEND_TOKEN

    def request(self, url, params=None, http_method=GET, user=None):
        params = params or {}
        headers = {'Authorization': 'Token {}'.format(self.token)}
        absolute_url = self.back_url + url
        response = {}

        if http_method == self.GET:
            response = requests.get(absolute_url, headers=headers, params=params)
        elif http_method == self.POST:
            headers['Content-Type'] = 'application/json'
            response = requests.post(absolute_url, headers=headers, json=params)
        elif http_method == self.PUT:
            headers['Content-Type'] = 'application/json'
            response = requests.put(absolute_url, headers=headers, json=params)
        else:
            assert 'Unsupported http method'

        try:
            content = json.loads(response.content.decode('utf-8'))
        except ValueError:
            logging.error('Invalid response content')
            raise BadRequestError('Invalid response content')

        if 'detail' in content:
            logging.error('Bad request: [{}]'.format(content))
            return {}

        return content

    def check_promo_code(self, promo_code):
        params = {'promo_code': promo_code}
        url = self.METHODS.get(self.CHECK_PROMO_URL)
        result = self.request(url, params=params)
        return result.get('exist', False)

    def create_guest(self, user):
        params = {'chat_id': user.chat_id, 'count': user.count, 'name': user.name}
        if user.promo_code:
            params['code'] = user.promo_code
        url = self.METHODS.get(self.CREATE_GUEST_URL)
        result = self.request(url, params=params, http_method=self.POST)
        return result

    def create_order(self, user):
        params = {'guest': user.id}
        url = self.METHODS.get(self.CREATE_ORDER_URL)
        result = self.request(url, params=params, http_method=self.POST)
        return result

    def activate_promoter(self, user, activate_code):
        params = {'chat_id': user.chat_id}
        url = self.METHODS.get(self.ACTIVATE_PROMOTER_URL).format(activate_code)
        result = self.request(url, params=params, http_method=self.PUT)
        return result

    def create_promocode(self, user, value):
        params = {'name': value, 'promoter': user.id}
        url = self.METHODS.get(self.CREATE_PROMOCODE_URL)
        result = self.request(url, params=params, http_method=self.POST)
        return result

    def get_statistic(self, user):
        url = self.METHODS.get(self.GET_STATISTIC_URL).format(user.id)
        result = self.request(url)
        return result


norma_api = NormaApi()
