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

    METHODS = {
        CHECK_PROMO_URL: 'web/check-promo-code/',
        CREATE_GUEST_URL: 'web/guests/',
        CREATE_ORDER_URL: 'web/orders/'
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

    # def authorization(self, user, password):
    #     params = {'domain': user.domain, 'password': password, 'username': user.username}
    #     url = self.METHODS.get(self.AUTH_URL)
    #
    #     result = self.request(url, params=params, http_method=self.POST)
    #
    #     token = result.get('token')
    #     if not token:
    #         return False
    #     user.token = token
    #     return True
    #
    # def update_profile(self, user):
    #     url = self.METHODS.get(self.PROFILE_URL)
    #     result = self.request(url, user=user)
    #     if not result:
    #         return None
    #     user.last_name = result.get('last_name')
    #     user.first_name = result.get('first_name')
    #     user.balance = result.get('balance')
    #     user.profile_id = result.get('id')
    #     user.role_type = result.get('role').get('type')
    #     return result
    #
    # def logout(self, user):
    #     url = self.METHODS.get(self.LOGOUT_URL)
    #     result = self.request(url, http_method=self.POST, user=user)
    #     return result
    #
    # def get_children(self, user):
    #     url = self.METHODS.get(self.CHILDREN_URL)
    #     result = self.request(url, user=user)
    #     return result
    #
    # def get_tasks(self, user, **kwargs):
    #     valid_params = ['date_0', 'date_1', 'kinds', 'trends', 'amount_0',
    #                     'amount_1', 'creators', 'executors', 'status']
    #     params = {key: kwargs[key] for key in kwargs.keys() if key in valid_params}
    #     url = self.METHODS.get(self.TASKS_URL)
    #     result = self.request(url, params=params, user=user)
    #     return result.get('tasks', [])
    #
    # def get_tasks_count(self, user, **kwargs):
    #     valid_params = ['date_0', 'date_1', 'kinds', 'trends', 'amount_0',
    #                     'amount_1', 'creators', 'executors', 'status']
    #     params = {key: kwargs[key] for key in kwargs.keys() if key in valid_params}
    #     url = self.METHODS.get(self.TASKS_COUNT_URL)
    #     result = self.request(url, params=params, user=user)
    #     return result
    #
    # def get_targets(self, user, **kwargs):
    #     valid_params = ['target_type', 'participants', 'archived']
    #     params = {key: kwargs[key] for key in kwargs.keys() if key in valid_params}
    #     url = self.METHODS.get(self.TARGET_URL)
    #     result = self.request(url, params=params, user=user)
    #     return result.get('results')
    #
    # def request_target(self, user, target_id):
    #     url = self.METHODS.get(self.TARGET_DETAIL_URL).format(target_id)
    #     result = self.request(url, http_method=self.PUT, user=user)
    #     return result
    #
    # def has_another_children(self, user):
    #     children_list = self.get_children(user)
    #     return len(children_list) > 1
    #
    # def children_statistics(self, user):
    #     url = self.METHODS.get(self.NAVIGATOR_URL)
    #     result = self.request(url, user=user)
    #     return result
    #
    # def task_formatting(self, tasks):
    #     result = []
    #     without_date = False
    #     for task in tasks:
    #         formatted_task = {}
    #         if task.get('kind') in [2, 3, 4, 6]:
    #             if task.get('deadline_dt'):
    #                 formatted_task['start_t'] = self._get_time(task['deadline_dt'])
    #                 formatted_task['finish_t'] = None
    #             else:
    #                 formatted_task['start_t'] = self._get_time(task['start_dt'])
    #                 formatted_task['finish_t'] = self._get_time(task['finish_dt'])
    #         else:
    #             formatted_task['finish_t'] = None
    #             formatted_task['start_t'] = None
    #             without_date = True
    #
    #         if not task['trend'] and task['kind'] == 6:
    #             formatted_task['trend'] = 'Посещение врача'
    #         else:
    #             formatted_task['trend'] = task['trend']['name']
    #         formatted_task['description'] = '' if not task['description'] else '\n>>' + task['description'] + '\n'
    #         result.append(formatted_task)
    #     return result if without_date else sorted(result, key=lambda x: x['start_t'])
    #
    # @staticmethod
    # def _get_time(value):
    #     time = value.split('T')[1]
    #     return time[:time.rfind(':')]
    #
    # @staticmethod
    # def has_valid_image(target):
    #     return (target.get('image_detail') and target['image_detail'].get('image')
    #             and target['image_detail']['image'].find('http://127.0.0.1') == -1)

norma_api = NormaApi()
