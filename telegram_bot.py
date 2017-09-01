import datetime
import telegram
import logging

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
    go_to_payment_another = 'Оплатить'

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
        except Exception as exc:
            self.reset_all_progress()
            logging.exception(exc)
            self.send_payment_type_carousel('Что-то пошло не так, придётся начать всё заново')
            return

    def execute_command(self):
        status = self.client.status
        if status is None:
            self.client.status = CacheUser.STARTED
            self.remove_keyboard_carousel('Сколько билетов вы хотите купить?')

        elif status == CacheUser.STARTED:
            count = self.message_text
            if not count.isdigit() or int(count) < 0:
                bot.send_message(self.chat_id, 'Введите число.')
                return
            self.client.count = int(count)
            self.send_payment_type_carousel('Выберите тип оплаты.')
            self.client.status = CacheUser.ENTER_COUNT

        elif status == CacheUser.ENTER_COUNT and self.client.count and \
                        self.message_text == self.with_promocode % (self.client.count * settings.COST_WITH_PROMO):
            self.client.status = CacheUser.ENTER_TYPE
            self.remove_keyboard_carousel('Введите промокод или "назад" для возврата')

        elif status == CacheUser.ENTER_TYPE and self.message_text.lower() == self.exit:
            self.reset_all_progress()

        elif status == CacheUser.ENTER_TYPE:
            promo_code = self.message_text.lower()
            status = self.check_promocode(promo_code)
            if not status:
                bot.send_message(self.chat_id, 'Вы ввели неверный промокод.')
                self.client.status = CacheUser.ENTER_COUNT
                self.send_payment_type_carousel('Выберите тип оплаты.')
            else:
                self.client.status = CacheUser.ENTER_PROMOCODE
                self.send_before_payment_carousel('Вы успешно ввели промокод. '
                                                  'Итоговая сумма: %s рублей' % (self.client.count * settings.COST_WITH_PROMO))

        elif status == CacheUser.ENTER_COUNT and self.client.count and \
                        self.message_text == self.without_promocode % (self.client.count * settings.COST_WITHOUT_PROMO):
            self.client.status = CacheUser.ENTER_PROMOCODE
            self.send_before_payment_carousel('Итоговая сумма: %s рублей' % (self.client.count * settings.COST_WITHOUT_PROMO))

        elif status == CacheUser.ENTER_PROMOCODE and self.message_text == self.go_to_payment:
            self.remove_keyboard_carousel('Введите имя по которому вы попадёте в список гостей.')
            self.client.status = CacheUser.ENTER_NAME

        elif status == CacheUser.ENTER_PROMOCODE and self.message_text == self.reset:
            self.client.status = CacheUser.STARTED
            self.client.delete(CacheUser.COUNT)
            self.client.delete(CacheUser.PROMO_CODE)
            self.reset_all_progress()

        elif status == CacheUser.ENTER_NAME:
            name = self.message_text
            self.client.name = name
            data = self.norma_api.create_guest(self.client)
            self.client.id = data.get('id')
            data_with_link = self.norma_api.create_order(self.client)
            bot.send_message(self.chat_id, 'Для оплаты перейдите по ссылке {}, платёжный терминал '
                                           'может взымает дополнительную комиссию (~2%)'.format(data_with_link.get('link')))
            self.client.status = CacheUser.START_PAYMENT
        elif status == CacheUser.START_PAYMENT and self.message_text == self.go_to_payment_another:
            self.send_another_payment_carousel('Подождите пока обрабатывается платёж, '
                                               'можете попробовать оплатить ещё раз.')
            data_with_link = self.norma_api.create_order(self.client)
            message = ('Для оплаты перейдите по ссылке {}, платёжный терминал '
                       'может взымает дополнительную комиссию (~2%)'.format(data_with_link.get('link')))
            self.remove_keyboard_carousel(message)
        elif status == CacheUser.START_PAYMENT:
            self.send_another_payment_carousel('Подождите пока обрабатывается платёж, '
                                               'можете попробовать оплатить ещё раз.')
        elif status == CacheUser.SUCCESS:
            bot.send_message(self.chat_id, 'Наше мероприятие состоится совсем скоро')

        else:
            self.reset_all_progress('Я не знаю такой команды, придётся начать всё заново.')

    def reset_all_progress(self, text=None):
        if text:
            bot.send_message(self.chat_id, text)
        if self.client.status < CacheUser.START_PAYMENT:
            self.client.status = CacheUser.STARTED
            self.client.delete(CacheUser.COUNT)
            self.client.delete(CacheUser.PROMO_CODE)
            self.client.delete(CacheUser.NAME)
            self.remove_keyboard_carousel('Сколько билетов вы хотите купить?')

    def send_payment_type_carousel(self, text):
        custom_keyboard = [[self.with_promocode % (self.client.count * settings.COST_WITH_PROMO)],
                           [self.without_promocode % (self.client.count * settings.COST_WITHOUT_PROMO)]]
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
        bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup)

    def remove_keyboard_carousel(self, text):
        reply_markup = telegram.ReplyKeyboardRemove()
        bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup)

    def send_before_payment_carousel(self, text):
        custom_keyboard = [[self.go_to_payment], [self.reset]]
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
        bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup)

    def send_another_payment_carousel(self, text):
        custom_keyboard = [[self.go_to_payment_another]]
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
        bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup)

    def check_promocode(self, promo_code):
        status = self.norma_api.check_promo_code(promo_code)
        if status:
            self.client.promo_code = promo_code
        return status


# class TelegramBot:
#     authenticate_command = 'Авторизоваться'
#     main_menu = 'Вернуться в Главное меню'
#     all_about_dragons = 'Все про дракончики'
#     all_about_targets = 'Все про цели'
#     all_about_tasks = 'Все про задания'
#     my_achievements = 'Хочу узнать про свои достижения'
#     bye_dragon = 'Пока, дракончик'
#     how_many_today_tasks = 'Сколько у меня заданий на сегодня?'
#     how_many_tomorrow_tasks = 'Сколько у меня заданий на завтра?'
#     active_tasks = 'Сколько у меня всего заданий ?'
#     my_today_shedule = 'Какое у меня расписание на сегодня ?'
#     unchecked_tasks = 'Сколько моих заданий еще не проверили родители ?'
#     my_tomorrow_shedule = 'Какое у меня расписание на завтра ?'
#     my_tasks_till_tomorrow = 'Какие задания мне нужно сделать до завтра ?'
#     my_tasks_without_dates = 'У меня есть задания без срока выполнения ?'
#     my_personal_target = 'Какая у меня личная цель ?'
#     my_collective_target = 'Какая у меня коллективная цель?'
#     how_many_money_to_target = 'Сколько мне нужно накопить на личную цель ?'
#     how_many_money_to_collective_target = 'Сколько мне осталось накопить на коллективную цель ?'
#     amount_of_dragons = 'Сколько у меня дракончиков ?'
#     other_dragons = 'Сколько дракончиков у других детей ?'
#     other_dragons_for_exercises = 'Сколько дракончиков за задачки у других детей ?'
#     amount_of_dragons_for_exercises = 'Сколько дракончиков за задачки у меня ?'
#     i_want_to_think = 'Нет, я еще подумаю'
#     i_want_to_wait = 'Нет, я подожду других'
#     back_to_dragons = 'Вернуться к дракончикам'
#     order_personal_target = 'Хочу! Заказать'
#     order_colective_tagret = 'Хочу! Внести дракончики'
#     how_many_dragons_from_other_children = 'Хочу узнать, кто уже внес дракончики'
#     bye = 'Пока'
#     back = 'Назад'
#     exit_command = 'Выйти'
#     request = dict
#
#     def __init__(self, request):
#         self.request = request.json
#         self.client = CacheUser(self.user_id, self.chat_id)
#         self.dragon_api = dragon_api
#
#     @property
#     def chat_id(self):
#         return self.request['message']['chat']['id']
#
#     @property
#     def user_id(self):
#         return self.request['message']['from']['id']
#
#     @property
#     def message_text(self):
#         return self.request['message']['text']
#
#     def parse_text_commands(self):
#         try:
#             self.execute_command()
#         except InvalidTokenError:
#             self.client.flush()
#             self.send_auth_message('Ты не авторизован, тебе нужно авторизоваться!')
#             return
#         except BadRequestError:
#             if self.client.is_authorized:
#                 self.send_child_carousel('Что-то мне нехорошо, не могу сосредоточиться.')
#             else:
#                 self.send_auth_message('Что-то мне нехорошо, не могу сосредоточиться.')
#             return
#         except Exception as exc:
#             logging.exception(exc)
#             if self.client.is_authorized:
#                 self.send_child_carousel('Что-то мне нехорошо, не могу сосредоточиться.')
#             else:
#                 self.send_auth_message('Что-то мне нехорошо, не могу сосредоточиться.')
#             return
#
#     def execute_command(self):
#
#         #Если пришла команда на авторизацию
#         if self.message_text == self.authenticate_command:
#             self.start_authenticate()
#
#         if not self.client.is_authorized:
#             self.check_auth_status()
#             return
#
#         # Все о достижениях
#         if self.message_text == self.my_achievements:
#             self.send_achievements_carousel('Что ты хочешь узнать про свои достижения?')
#
#         # Все про дракончики
#         elif self.message_text == self.all_about_dragons:
#             self.send_all_about_dragons_carousel('Что ты хочешь узнать про дракончики?')
#
#         # Все про цели
#         elif self.message_text == self.all_about_targets:
#             self.send_all_about_targets_carousel('Что ты хочешь узнать про цели?')
#
#         # Цели: личная цель
#         elif self.message_text == self.my_personal_target:
#             targets = self.dragon_api.get_targets(self.client, target_type=0,
#                                                   archived='false', participants=self.client.profile_id)
#             if not targets:
#                 bot.send_message(self.chat_id, 'Ее пока нет, предложи родителям что-нибудь интересное.')
#                 return
#             target = targets[0]
#             if target:
#                 if self.dragon_api.has_valid_image(target):
#                     bot.send_photo(self.chat_id, target['image_detail']['image'],
#                                    caption='Твоя личная цель сейчас - {}.'.format(target['name']))
#                 else:
#                     bot.send_message(self.chat_id, 'Твоя личная цель сейчас - {}.'.format(target['name']))
#
#         # Цели: сколько дракончиков до личной цели
#         elif self.message_text == self.how_many_money_to_target:
#             targets = self.dragon_api.get_targets(self.client, target_type=0,
#                                                   archived='false', participants=self.client.profile_id)
#             if not targets:
#                 bot.send_message(self.chat_id, 'Хочешь копить на что-то классное? Сначала выбери цель!')
#                 return
#
#             target = targets[0]
#             participant = target['participants'][0]
#             if participant.get('requested'):
#                 bot.send_message(self.chat_id, 'Ты уже заказал цель, нужно немного подождать!')
#                 return
#
#             self.dragon_api.update_profile(self.client)
#             total_amount = Decimal(participant.get('total'))
#             dragons_left = total_amount - Decimal(self.client.balance)
#
#             if dragons_left > 0:
#                 bot.send_message(self.chat_id,
#                                  'Тебе осталось накопить {} дракончиков.'.format(str(dragons_left).split('.')[0]))
#             # TODO: кнопка покупки
#             elif dragons_left <= 0:
#                 self.send_buy_personal_target_carousel('Вау, у тебя уже достаточно дракончиков для этой цели.'
#                                                        'Хочешь заказать цель ?')
#
#         # Цели: коллективная цель
#         elif self.message_text == self.my_collective_target:
#             targets = self.dragon_api.get_targets(self.client, target_type=1,
#                                                   archived='false', participants=self.client.profile_id)
#             if not targets:
#                 bot.send_message(self.chat_id, 'Я везде посмотрел, но коллективную цель не нашел.')
#                 return
#
#             target = targets[0]
#             if target:
#                 if self.dragon_api.has_valid_image(target):
#                     bot.send_photo(self.chat_id, target['image_detail']['image'],
#                                    caption='Ты копишь дракончики на  - {}.'.format(target['name']))
#                 else:
#                     bot.send_message(self.chat_id, 'Ты копишь дракончики на - {}.'.format(target['name']))
#
#         # Цели: сколько дракончиков до коллективной цели
#         elif self.message_text == self.how_many_money_to_collective_target:
#             targets = self.dragon_api.get_targets(self.client, target_type=1,
#                                                   archived='false', participants=self.client.profile_id)
#
#             if not targets:
#                 bot.send_message(self.chat_id, 'Коллективная цель? Какая коллективная цель ?'
#                                                'Выберите что-нибудь и сразу начнем копить.')
#                 return
#
#             target = targets[0]
#             participant = [p for p in target['participants'] if p['profile_detail']['id'] == self.client.profile_id][0]
#             if participant.get('requested'):
#                 bot.send_message(self.chat_id, 'Ты уже внёс свою часть, нужно немного подождать '
#                                                'пока другие накопят дракончиков!')
#                 return
#
#             self.dragon_api.update_profile(self.client)
#             total_amount = Decimal(participant.get('total'))
#             dragons_left = total_amount - Decimal(self.client.balance)
#
#             if dragons_left > 0:
#                 bot.send_message(self.chat_id,
#                                  'Еще {} дракончиков и свою часть ты честно отработал(а).'.format(str(dragons_left).split('.')[0]))
#             # TODO: кнопка покупки
#             elif dragons_left <= 0:
#                 self.send_buy_collective_target_carousel('Все дракончики в сборе. Хочешь внести дракончики?'
#                                                          ' Остальные внесли, дело за тобой.)')
#
#         # Цели (меню цели): посмотреть сколько детей вложили деньги
#         elif self.message_text == self.how_many_dragons_from_other_children:
#             reply_string = ''
#             targets = self.dragon_api.get_targets(self.client, target_type=1,
#                                                   archived='false', participants=self.client.profile_id)
#
#             if not targets:
#                 bot.send_message(self.chat_id, 'Коллективная цель? Какая коллективная цель ?'
#                                                'Выберите что-нибудь и сразу начнем копить.')
#                 return
#
#             target = targets[0]
#             participants = [p for p in target['participants'] if p['profile_detail']['id'] != self.client.profile_id]
#
#             for participant in participants:
#                 if participant['requested']:
#                     reply_string += '{}:\t {} дракончиков\n'.format(participant['profile_detail']['first_name'],
#                                                                     participant['total'].split('.')[0])
#                 else:
#                     reply_string += '{}:\t еще не внес(ла) дракончики\n'.format(
#                         participant['profile_detail']['first_name'])
#             bot.send_message(self.chat_id, reply_string)
#
#         # Цели (меню цели): нажатие на кнопку 'Я хочу подумать' или 'Я хочу подождать других детей'
#         elif ((self.message_text == self.i_want_to_wait or
#               self.message_text == self.i_want_to_think)):
#             self.send_all_about_targets_carousel('Хорошо')
#
#         # Цели (меню цели): вернуться из меню одной цели в меню нескольких целей
#         elif self.message_text == self.back_to_dragons:
#             self.send_all_about_targets_carousel('Что еще ты хочешь узнать про цели?')
#
#         # Цели (меню цели): заказать личную цель
#         elif self.message_text == self.order_personal_target:
#             targets = self.dragon_api.get_targets(self.client, target_type=0,
#                                                   archived='false', participants=self.client.profile_id)
#             if not targets:
#                 bot.send_message(self.chat_id, 'Хочешь копить на что-то классное? Сначала выбери цель!')
#                 return
#
#             target = targets[0]
#             participant = target['participants'][0]
#             if participant.get('requested'):
#                 bot.send_message(self.chat_id, 'Ты уже заказал цель, нужно немного подождать!')
#                 return
#
#             self.dragon_api.update_profile(self.client)
#             total_amount = Decimal(participant.get('total'))
#             dragons_left = total_amount - Decimal(self.client.balance)
#
#             if dragons_left > 0:
#                 bot.send_message(self.chat_id,
#                                  'Тебе осталось накопить {} дракончиков.'.format(str(dragons_left).split('.')[0]))
#                 return
#
#             status = self.dragon_api.request_target(self.client, target['id'])
#             if status:
#                 self.send_all_about_targets_carousel('Ты заказал {} за {} дракончиков. Родителям я уже сказал!'.
#                                                      format(target['name'], total_amount))
#             else:
#                 self.send_all_about_targets_carousel('Не получилось заказать цель.')
#
#         # Цели (меню цели): заказать коллективную цель
#         elif self.message_text == self.order_colective_tagret:
#             targets = self.dragon_api.get_targets(self.client, target_type=1,
#                                                   archived='false', participants=self.client.profile_id)
#
#             if not targets:
#                 bot.send_message(self.chat_id, 'Коллективная цель? Какая коллективная цель ?'
#                                                'Выберите что-нибудь и сразу начнем копить.')
#                 return
#
#             target = targets[0]
#             participant = [p for p in target['participants'] if p['profile_detail']['id'] == self.client.profile_id][0]
#             if participant.get('requested'):
#                 bot.send_message(self.chat_id, 'Ты уже внёс свою часть, нужно немного подождать '
#                                                'пока другие накопят дракончиков!')
#                 return
#
#             self.dragon_api.update_profile(self.client)
#             total_amount = Decimal(participant.get('total'))
#             dragons_left = total_amount - Decimal(self.client.balance)
#
#             if dragons_left > 0:
#                 bot.send_message(self.chat_id, 'Еще {} дракончиков и свою часть ты честно отработал(а).'.format(
#                                      str(dragons_left).split('.')[0]))
#
#             status = self.dragon_api.request_target(self.client, target['id'])
#             if status:
#                 self.send_all_about_targets_carousel('Ты заказал {} за {} дракончиков. Родителям я уже сказал!'.
#                                                      format(target['name'], total_amount))
#             else:
#                 self.send_all_about_targets_carousel('Не получилось заказать цель.')
#
#         # Все про задачи
#         elif self.message_text == self.all_about_tasks:
#             self.send_all_about_tasks_carousel('Что ты хочешь узнать про задания?')
#
#         # Задачи: Активные задачи
#         elif self.message_text == self.active_tasks:
#             tasks_counts = self.dragon_api.get_tasks_count(self.client, executors=self.client.profile_id,)
#             active_tasks_count = tasks_counts.get('active_tasks')
#             if active_tasks_count > 0:
#                 bot.send_message(self.chat_id, 'У тебя {} активных заданий(я). '
#                                                'Больше заданий - больше дракончиков.'.format(active_tasks_count))
#             else:
#                 bot.send_message(self.chat_id, 'Пока никаких заданий, загляни позже.')
#
#         # Задачи: Задачи на сегодня
#         elif self.message_text == self.how_many_today_tasks:
#             today = datetime.date.today().strftime('%d.%m.%Y')
#             tasks_counts = self.dragon_api.get_tasks_count(self.client, executors=self.client.profile_id,
#                                                            date_0=today,  date_1=today)
#             active_tasks_count = tasks_counts.get('active_tasks')
#             if active_tasks_count < 1:
#                 bot.send_message(self.chat_id, 'Все задания на сегодня выполнены!')
#             else:
#                 bot.send_message(self.chat_id, 'У тебя {} активных заданий(я). Вперед!'.format(active_tasks_count))
#
#         # Задачи: Непроверенные задачи
#         elif self.message_text == self.unchecked_tasks:
#             tasks_counts = self.dragon_api.get_tasks_count(self.client, executors=self.client.profile_id)
#             done_tasks_count = tasks_counts.get('done_tasks')
#             if done_tasks_count < 1:
#                 bot.send_message(self.chat_id, 'Родители уже проверили все задания.')
#             else:
#                 bot.send_message(self.chat_id, 'На проверке еще {} заданий(я).'.format(done_tasks_count))
#
#         # Задачи: Задачи на завтра
#         elif self.message_text == self.how_many_tomorrow_tasks:
#             tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%d.%m.%Y')
#             tasks_counts = self.dragon_api.get_tasks_count(self.client, executors=self.client.profile_id,
#                                                            date_0=tomorrow, date_1=tomorrow)
#             active_tasks_count = tasks_counts.get('active_tasks')
#             if active_tasks_count < 1:
#                 bot.send_message(self.chat_id, 'Все задания на завтра выполнены!')
#             else:
#                 bot.send_message(self.chat_id, 'У тебя {} активных заданий(я). Вперед!'.format(active_tasks_count))
#
#         # Задачи: Расписание на сегодня
#         elif self.message_text == self.my_today_shedule:
#             task_string = ''
#             today = datetime.date.today().strftime('%d.%m.%Y')
#             tasks = self.dragon_api.get_tasks(self.client, executors=self.client.profile_id,
#                                               date_0=today,  date_1=today, status=1)
#             if not tasks:
#                 bot.send_message(self.chat_id, 'На сегодня планов нет, я все проверил.')
#                 return
#
#             formatted_tasks = self.dragon_api.task_formatting(tasks)
#             for task in formatted_tasks:
#                 if task['finish_t']:
#                     time = '{} - {}'.format(task['start_t'], task['finish_t'])
#                 else:
#                     time = 'до {}'.format(task['start_t'])
#                 task_string += '{}\t: {}\t {}\n'.format(time, task['trend'], task['description'])
#
#             bot.send_message(self.chat_id, 'Смотри сколько дел, у тебя сегодня:\n{}'.format(task_string))
#
#         # Задачи: Расписание на завтра
#         elif self.message_text == self.my_tomorrow_shedule:
#             task_string = ''
#             tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%d.%m.%Y')
#             tasks = self.dragon_api.get_tasks(self.client, executors=self.client.profile_id,
#                                               date_0=tomorrow, date_1=tomorrow, status=1)
#             if not tasks:
#                 bot.send_message(self.chat_id, 'На завтра планов нет, я все проверил.')
#                 return
#
#             formatted_tasks = self.dragon_api.task_formatting(tasks)
#             for task in formatted_tasks:
#                 if task['finish_t']:
#                     time = '{} - {}'.format(task['start_t'], task['finish_t'])
#                 else:
#                     time = 'до {}'.format(task['start_t'])
#                 task_string += '{}\t: {}\t {}\n'.format(time, task['trend'], task['description'])
#
#             bot.send_message(self.chat_id, 'Смотри сколько дел, у тебя завтра:\n{}'.format(task_string))
#
#         # Задачи: Задачи до завтра
#         elif self.message_text == self.my_tasks_till_tomorrow:
#             task_string = ''
#             today = datetime.date.today().strftime('%d.%m.%Y')
#             tasks = self.dragon_api.get_tasks(self.client, executors=self.client.profile_id,
#                                               date_0=today, date_1=today, status=1, kinds='2, 3, 4')
#             if not tasks:
#                 bot.send_message(self.chat_id, 'Молодец ! Все уже сделано.')
#                 return
#
#             formatted_tasks = self.dragon_api.task_formatting(tasks)
#             for task in formatted_tasks:
#                 if task['finish_t']:
#                     time = 'до {}'.format(task['finish_t'])
#                 else:
#                     time = 'до {}'.format(task['start_t'])
#                 task_string += '{}\t {}\t {}\n'.format(task['trend'], time, task['description'])
#             bot.send_message(self.chat_id, 'Ой-ой-ой, '
#                                            'тебе нужно успеть выполнить задания:\n{}'.format(task_string))
#
#         # Задачи: Задачи без даты
#         elif self.message_text == self.my_tasks_without_dates:
#             task_string = ''
#             tasks = self.dragon_api.get_tasks(self.client, executors=self.client.profile_id, status=1, kinds=1)
#             if not tasks:
#                 bot.send_message(self.chat_id, 'Таких заданий нет, проверь другие!')
#                 return
#             formatted_tasks = self.dragon_api.task_formatting(tasks)
#             for task in formatted_tasks:
#                 task_string += '{}\t {}\n'.format(task['trend'], task['description'])
#             bot.send_message(self.chat_id, 'Как найдешь время - сразу на охоту за дракончиками!'
#                                            'Вот твои задания :\n{}'.format(task_string))
#
#         # Дракончики: сколько у меня дракончиков
#         elif self.message_text == self.amount_of_dragons:
#             data = self.dragon_api.update_profile(self.client)
#             if not data:
#                 return
#             bot.send_message(self.chat_id, 'У тебя сейчас {} дракончиков.'.format(self.client.balance))
#
#         # Дракончиков за задачки у ребёнка
#         elif self.message_text == self.amount_of_dragons_for_exercises:
#             children_statistic = self.dragon_api.children_statistics(self.client)
#             client_statistic = [child for child in children_statistic if child['id'] == self.client.profile_id][0]
#             library_sum_dragons = int(client_statistic['library_sum_dragons'])
#             if library_sum_dragons:
#                 bot.send_message(self.chat_id, 'У тебя {} дракончиков. Кто тут самый умный?'.format(
#                     library_sum_dragons))
#             else:
#                 bot.send_message(self.chat_id, 'Ни один дракончик с задачек не прилетал')
#
#         # Дракончиков за задачки у других детей
#         elif self.message_text == self.other_dragons_for_exercises:
#             children_statistic = self.dragon_api.children_statistics(self.client)
#             reply_string = ''
#             for child in children_statistic:
#                 if child['id'] != self.client.profile_id:
#                     reply_string += 'У {} {} дракончиков\n'.format(
#                         child['first_name'], int(child['library_sum_dragons']))
#             bot.send_message(self.chat_id, reply_string)
#
#         # Дракончики: сколько дракончиков у других детей
#         elif self.message_text == self.other_dragons:
#             children_statistic = self.dragon_api.children_statistics(self.client)
#             reply_string = ''
#             for child in children_statistic:
#                 if child['id'] != self.client.profile_id:
#                     reply_string += '{}: {} дракончиков\n'.format(child['first_name'], child['balance'].split('.')[0])
#             bot.send_message(self.chat_id, reply_string)
#
#         # Достижения: главное меню
#         elif self.message_text == self.main_menu:
#             self.send_child_carousel('Главное меню.')
#
#         # Если команда назад
#         elif self.message_text == self.back:
#             self.send_achievements_carousel('Что еще ты хочешь узнать про свои достижения?')
#
#         # Если команда выхода
#         elif self.message_text in [self.exit_command, self.bye, self.bye_dragon]:
#             status = self.dragon_api.logout(self.client)
#             if status:
#                 self.client.flush()
#                 self.send_auth_message('Пока :(')
#
#         # Если какая-то тарабарщина
#         else:
#             bot.send_message(self.chat_id, 'Я не знаю такой команды.')
#
#     def check_auth_status(self):
#         status = self.client.status
#         if status == CacheUser.AUTHORIZED:
#             return
#         if status is None:
#             self.send_auth_message('Ты не авторизован, тебе нужно авторизоваться!')
#         elif status == CacheUser.AUTH_STARTED:
#             self.ask_for_domain()
#         elif status == CacheUser.DOMAIN_SENT:
#             domain = self.message_text.lower()
#             if self.dragon_api.check_domain(domain):
#                 self.client.domain = domain
#                 self.ask_for_login()
#             else:
#                 self.stop_auth(wrong_domain=True)
#         elif status == CacheUser.LOGIN_SENT:
#             self.client.username = self.message_text.lower()
#             self.ask_for_password()
#
#         elif status == CacheUser.PASSWORD_SENT:
#             self.authenticate_user(self.message_text.lower())
#
#     def stop_auth(self, wrong_domain=False, wrong_login=False):
#         self.client.stop_auth()
#         if wrong_login:
#             self.send_auth_message('Такого логина нет в этой семье, попробуй еще раз.')
#         if wrong_domain:
#             self.send_auth_message('Такой семьи нет, попробуй еще раз.')
#
#     def ask_for_domain(self):
#         reply_markup = telegram.ReplyKeyboardRemove()
#         bot.send_message(self.chat_id, 'Введи логин семьи', reply_markup=reply_markup)
#         self.client.status = CacheUser.DOMAIN_SENT
#
#     def ask_for_login(self):
#         reply_markup = telegram.ReplyKeyboardRemove()
#         bot.send_message(self.chat_id, 'Введи логин', reply_markup=reply_markup)
#         self.client.status = CacheUser.LOGIN_SENT
#
#     def ask_for_password(self):
#         bot.send_message(self.user_id, 'Введи пароль')
#         self.client.status = CacheUser.PASSWORD_SENT
#
#     def authenticate_user(self, password):
#         is_auth = self.dragon_api.authorization(self.client, password)
#         if not is_auth:
#             self.client.flush()
#             self.send_auth_message('Логин и пароль не совпадают, попробуйте снова.')
#             return
#
#         self.dragon_api.update_profile(self.client)
#         bot.send_message(self.chat_id, 'Привет, {} {}, ты авторизовался.'.format(self.client.last_name,
#                                                                                  self.client.first_name))
#         if self.client.role_type == 'c':
#             self.send_child_carousel('{}, что мы будем делать?'.format(self.client.first_name))
#             self.client.status = CacheUser.AUTHORIZED
#         else:
#             self.client.flush()
#             self.send_auth_message('С аккаунта взрослого нельзя попасть в бота.')
#
#     def start_authenticate(self):
#         if self.client.is_authorized:
#             self.client.delete(CacheUser.TOKEN)
#         self.client.start_authorization()
#
#     def send_all_about_tasks_carousel(self, text):
#         # TODO: разобраться с расписанием
#         # [self.my_today_shedule],[self.my_tomorrow_shedule],
#         custom_keyboard = [[self.my_today_shedule], [self.my_tomorrow_shedule], [self.unchecked_tasks],
#                            [self.how_many_today_tasks], [self.how_many_tomorrow_tasks], [self.active_tasks],
#                            [self.my_tasks_till_tomorrow], [self.my_tasks_without_dates], [self.back]]
#         reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
#         bot.send_message(chat_id=self.chat_id,
#                          text=text,
#                          reply_markup=reply_markup)
#
#     def send_all_about_targets_carousel(self, text):
#         custom_keyboard = [[self.my_personal_target], [self.how_many_money_to_target],
#                            [self.my_collective_target], [self.how_many_money_to_collective_target],
#                            [self.back]]
#         reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
#         bot.send_message(chat_id=self.chat_id,
#                          text=text,
#                          reply_markup=reply_markup)
#
#     def send_all_about_dragons_carousel(self, text):
#         custom_keyboard = [[self.amount_of_dragons], [self.amount_of_dragons_for_exercises]]
#         if self.dragon_api.has_another_children(self.client):
#             custom_keyboard.extend([[self.other_dragons], [self.other_dragons_for_exercises], [self.back]])
#         else:
#             custom_keyboard.append([self.back])
#
#         reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
#         bot.send_message(chat_id=self.chat_id,
#                          text=text,
#                          reply_markup=reply_markup)
#
#     def send_achievements_carousel(self, text):
#         custom_keyboard = [[self.all_about_dragons], [self.all_about_targets],
#                            [self.all_about_tasks], [self.main_menu]]
#         reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
#         bot.send_message(chat_id=self.chat_id,
#                          text=text,
#                          reply_markup=reply_markup)
#
#     def send_buy_personal_target_carousel(self, text):
#         custom_keyboard = [[self.order_personal_target], [self.i_want_to_think]]
#         reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
#         bot.send_message(chat_id=self.chat_id,
#                          text=text,
#                          reply_markup=reply_markup)
#
#     def send_buy_collective_target_carousel(self, text):
#         custom_keyboard = [[self.order_colective_tagret], [self.i_want_to_wait],
#                            [self.how_many_dragons_from_other_children]]
#         reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
#         bot.send_message(chat_id=self.chat_id,
#                          text=text,
#                          reply_markup=reply_markup)
#
#     def send_auth_message(self, text):
#         custom_keyboard = [[self.authenticate_command]]
#         reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
#         bot.send_message(chat_id=self.chat_id,
#                          text=text,
#                          reply_markup=reply_markup)
#
#     def send_child_carousel(self, text):
#         custom_keyboard = [[self.my_achievements], [self.bye_dragon]]
#         reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
#         bot.send_message(chat_id=self.chat_id,
#                          text=text,
#                          reply_markup=reply_markup)
#
#     @classmethod
#     def get_date(cls, date):
#         return datetime.datetime.strptime(date.split('T')[0], '%Y-%m-%d').date()
