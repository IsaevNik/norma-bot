import time
import telegram
import logging

from telegram import InlineKeyboardButton
from telegram.error import Unauthorized, TelegramError

import settings

from app import bot

from user import CacheUser
from integrations import norma_api, BadRequestError


class TelegramBot:
    with_promocode = 'С промокодом %dр'
    without_promocode = 'Без промокода %dр'
    go_to_payment = 'Перейти к оплате'
    exit = 'назад'
    reset = 'Вернуться в начало'
    go_to_payment_another = 'Получить новую ссылку'
    buy_ticket = 'Купить билет'
    way = 'Как добраться'
    line_up = 'Line up'
    facebook_link = 'Ссылка на мероприятие'
    get_statistic = 'Получить статистику'
    hello_message = 'Вас приветствует команда NORMA! ' \
                    'Здесь вы можете узнать подробную информацию, а так же преобрести билеты ' \
                    'на предстоящее мероприятие.\n' \
                    '29.12 - {}'.format(settings.EVENT_LINK)
    map_url = 'https://scontent-arn2-1.xx.fbcdn.net/v/t1.0-9/21751747_239090976615586_6157852026952517567_n.jpg?' \
              'oh=ea7d664fac08b283de40aa0232082bd6&oe=5ABFADA8'

    def __init__(self, request):
        self.request = request.json
        self.client = CacheUser(self.user_id, self.chat_id)
        self.norma_api = norma_api

    @property
    def chat_id(self):
        return self.request['message']['chat']['id']

    @property
    def user_id(self):
        return self.request['message']['from']['id']

    @property
    def message_text(self):
        return self.request['message']['text']

    def parse_text_commands(self):

        try:
            self.execute_command()
        except TelegramError as exc:
            logging.exception(exc)
            return
        except Exception as exc:
            self.reset_all_progress('Что то пошло не так')
            logging.exception(exc)
            return

    def execute_command(self):
        status = self.client.status
        if status is None:
            self.client.status = CacheUser.STARTED
            self.send_main_menu_for_started(self.hello_message)

        elif status in [CacheUser.STARTED, CacheUser.SUCCESS] and self.message_text == self.facebook_link:
            bot.send_message(self.chat_id, settings.EVENT_LINK)

        elif status in [CacheUser.STARTED, CacheUser.SUCCESS] and self.message_text == self.line_up:
            bot.send_message(self.chat_id, settings.LINE_UP_DETAIL)

        elif status in [CacheUser.STARTED, CacheUser.SUCCESS] and self.message_text == self.way:
            bot.send_message(self.chat_id, 'Москва, Подкопаевский переулок, 4, стр 7')
            bot.send_location(self.chat_id, latitude=55.753724, longitude=37.641641)

        elif status == CacheUser.STARTED and self.message_text == self.buy_ticket:
            if settings.FINISH_SALE:
                bot.send_message(self.client.id, 'Продажа билетов окончена')
                return
            # self.remove_keyboard_carousel('')
            self.send_numeric_carousel('Сколько билетов вы хотите купить?')
            self.client.status = CacheUser.BUY_TICKET

        elif self.message_text == self.reset:
            self.reset_all_progress('Выберите действие')

        elif status == CacheUser.BUY_TICKET:
            value = self.message_text
            if not value.isdigit() or int(value) < 0:
                bot.send_message(self.chat_id, 'Введите число.')
                return
            self.client.count = int(value)
            self.client.status = CacheUser.ENTER_COUNT
            self.send_before_payment_carousel(
                'Итоговая сумма: %s рублей.' % (self.client.count * settings.COST_WITHOUT_PROMO))

        elif status == CacheUser.STARTED:
            self.send_main_menu_for_started('Выберите действие')

        elif status == CacheUser.ENTER_COUNT and self.message_text == self.go_to_payment:
            self.send_reset_carousel('Введите имя по которому вы попадёте в список гостей.')
            self.client.status = CacheUser.ENTER_NAME

        # elif self.client.is_promoter and status == CacheUser.STARTED:
        #     promo_code = self.message_text.lower().strip()
        #     if not promo_code.isalnum():
        #         bot.send_message(self.chat_id, 'Недопустимые символы, введите заново.')
        #         return
        #     name = self.create_promocode(promo_code)
        #     if not name:
        #         bot.send_message(self.chat_id, 'Недопустимые символы, введите заново.')
        #         return
        #     self.client.status = CacheUser.SUCCESS
        #     self.send_statistic_carousel('Отлично, Ваш промокод [{}] сохранён.'.format(name))

        # elif status == CacheUser.STARTED:
        #     value = self.message_text
        #     if not value.isdigit() and not settings.ALL_PROMOTER_HERE:
        #         status = self.check_promoter(value)
        #         if status:
        #             bot.send_message(self.chat_id, 'Теперь вы промоутер Norma. Введите промокод (латинские символы и цифры)')
        #             return
        #     if not value.isdigit() or int(value) < 0:
        #         bot.send_message(self.chat_id, 'Введите число.')
        #         return
        #     self.client.count = int(value)
        #     self.send_payment_type_carousel('Выберите тип оплаты.')
        #     self.client.status = CacheUser.ENTER_COUNT

        # elif status == CacheUser.ENTER_COUNT and self.client.count and \
        #                 self.message_text == self.with_promocode % (self.client.count * settings.COST_WITH_PROMO):
        #     self.client.status = CacheUser.ENTER_TYPE
        #     self.send_reset_carousel('Введите промокод или вернитесь в начало.')

        # elif status == CacheUser.ENTER_TYPE and self.message_text == self.reset:
        #     self.reset_all_progress()
        #
        # elif status == CacheUser.ENTER_TYPE:
        #     promo_code = self.message_text.lower()
        #     status = self.check_promocode(promo_code)
        #     if not status:
        #         bot.send_message(self.chat_id, 'Вы ввели неверный промокод.')
        #         self.client.status = CacheUser.ENTER_COUNT
        #         self.send_payment_type_carousel('Выберите тип оплаты.')
        #     else:
        #         self.client.status = CacheUser.ENTER_PROMOCODE
        #         self.send_before_payment_carousel('Вы успешно ввели промокод. '
        #                                           'Итоговая сумма: %s рублей.' % (self.client.count * settings.COST_WITH_PROMO))

        # elif status == CacheUser.ENTER_COUNT and self.client.count and \
        #                 self.message_text == self.without_promocode % (self.client.count * settings.COST_WITHOUT_PROMO):
        #     self.client.status = CacheUser.ENTER_PROMOCODE
        #     self.send_before_payment_carousel('Итоговая сумма: %s рублей.' % (self.client.count * settings.COST_WITHOUT_PROMO))
        #
        # elif status == CacheUser.ENTER_PROMOCODE and self.message_text == self.go_to_payment:
        #     self.send_reset_carousel('Введите имя по которому вы попадёте в список гостей.')
        #     self.client.status = CacheUser.ENTER_NAME

        # elif status == CacheUser.ENTER_PROMOCODE and self.message_text == self.reset:
        #     self.reset_all_progress()
        #
        # elif status == CacheUser.ENTER_NAME and self.message_text == self.reset:
        #     self.reset_all_progress()

        elif status == CacheUser.ENTER_NAME:
            name = self.message_text
            self.client.name = name
            data = self.norma_api.create_guest(self.client)
            self.client.id = data.get('id')
            data_with_link = self.norma_api.create_order(self.client)
            bot.send_message(self.chat_id, 'Для оплаты перейдите по ссылке {}'.format(data_with_link.get('link')))
            self.client.status = CacheUser.START_PAYMENT
            self.send_another_payment_carousel('Ваш личный код будет отправлен после обработки платежа.'
                                               ' Если ссылка не работает, вы можете получить еще одну.')

        elif status == CacheUser.START_PAYMENT and self.message_text == self.go_to_payment_another:
            data_with_link = self.norma_api.create_order(self.client)
            message = ('Для оплаты перейдите по ссылке {}'.format(data_with_link.get('link')))
            bot.send_message(self.chat_id, message)
            self.send_another_payment_carousel('Ваш личный код будет отправлен после обработки платежа.'
                                               ' Если ссылка не работает, вы можете получить еще одну.')

        # elif status == CacheUser.START_PAYMENT and self.message_text == self.reset:
        #     self.reset_all_progress('Выберите действие')

        # elif status == CacheUser.SUCCESS and self.client.is_promoter and self.message_text == self.get_statistic:
        #     statistic = self.norma_api.get_statistic(self.client)
        #     bot.send_message(self.chat_id, 'Ваш промокод успешно активировало {} человек. Выплата: {} р'.format(
        #         statistic['guests_count'], statistic['total_payment']))
        #
        # elif status == CacheUser.SUCCESS and self.client.is_promoter:
        #     self.send_statistic_carousel('Для получения статистики нажмите кнопку.')

        # elif status == CacheUser.SUCCESS:
        #     self.send_main_menu_for_successed('Наше мероприятие состоится совсем скоро.')

        else:
            self.reset_all_progress('Я не знаю такой команды, придётся начать всё заново.')

    def reset_all_progress(self, text=None):
        if self.client.status <= CacheUser.START_PAYMENT:
            self.client.status = CacheUser.STARTED
            self.client.delete(CacheUser.COUNT)
            self.client.delete(CacheUser.PROMO_CODE)
            self.client.delete(CacheUser.NAME)
            self.client.delete(CacheUser.ID)
            self.send_main_menu_for_started(text)
        else:
            self.send_main_menu_for_successed(text)
            # self.send_numeric_carousel('Сколько билетов вы хотите купить?')

    def send_payment_type_carousel(self, text):
        custom_keyboard = [[self.with_promocode % (self.client.count * settings.COST_WITH_PROMO)],
                           [self.without_promocode % (self.client.count * settings.COST_WITHOUT_PROMO)]]
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
        bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup)

    def remove_keyboard_carousel(self, text):
        reply_markup = telegram.ReplyKeyboardRemove()
        bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup)

    def send_numeric_carousel(self, text):
        custom_keyboard = [['1', '2', '3'], ['4', '5', '6'], ['7', '8', '9'], [self.reset]]
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
        bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup)

    def send_before_payment_carousel(self, text):
        custom_keyboard = [[self.go_to_payment], [self.reset]]
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
        bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup)

    def send_statistic_carousel(self, text):
        custom_keyboard = [[self.get_statistic],]
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
        bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup)

    def send_reset_carousel(self, text):
        custom_keyboard = [[self.reset],]
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
        bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup)

    def send_another_payment_carousel(self, text):
        custom_keyboard = [[self.go_to_payment_another], [self.reset]]
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
        bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup)

    def send_main_menu_for_started(self, text):
        custom_keyboard = [[self.line_up],
                           [self.way],
                           [self.facebook_link]]
        if not settings.FINISH_SALE:
            custom_keyboard.insert(0, [self.buy_ticket])
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
        bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup)

    def send_main_menu_for_successed(self, text):
        custom_keyboard = [[self.line_up],
                           [self.way],
                           [self.facebook_link]]
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
        bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup)

    def check_promocode(self, promo_code):
        status = self.norma_api.check_promo_code(promo_code)
        if status:
            self.client.promo_code = promo_code
        return status

    def check_promoter(self, value):
        data = self.norma_api.activate_promoter(self.client, value.lower())
        if not data:
            return False
        self.client.is_promoter = 1
        self.client.id = data['id']
        return True

    def create_promocode(self, value):
        data = self.norma_api.create_promocode(self.client, value)
        if not data:
            return False
        return data['name']

    @classmethod
    def send_advert(cls, message=None, photo_url=None, with_reset=True):
        message = message or settings.ADVERT_MESSAGE
        photo_url = photo_url or settings.ADVERT_IMAGE
        for user in CacheUser.get_all():
            try:
                cls.send_main_menu(user.chat_id, message)
                bot.send_photo(user.chat_id, photo_url)
                time.sleep(1)
                if with_reset:
                    user.refresh()
            except TelegramError:
                print(user.chat_id)
            except Exception:
                print(user.chat_id)

    @classmethod
    def send_main_menu(cls, chat_id, text, with_buying=True):
        custom_keyboard = [[cls.line_up],
                           [cls.way],
                           [cls.facebook_link]]
        if not settings.FINISH_SALE and with_buying:
            custom_keyboard.insert(0, [cls.buy_ticket])
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
        bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

    @classmethod
    def reset_all(cls):
        for user in CacheUser.get_all():
            user.refresh()
