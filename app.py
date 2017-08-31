#!/usr/bin/env python
import telegram
import logging
import json
import time
import os
from flask import Flask, request
from settings import HOST, PORT, TOKEN
from utils import check_auth

app = Flask(__name__)
bot = telegram.Bot(token=TOKEN)


@app.route('/')
def hello():
    return 'Ngrok was successfully set'


@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    from telegram_bot import TelegramBot
    telegram_bot = TelegramBot(request)
    telegram_bot.parse_text_commands()
    return 'Ok'


@app.route('/send/success/', methods=['POST'])
@check_auth
def send_success():
    from user import CacheUser
    data = json.loads(request.data.decode('utf-8'))
    user = CacheUser(data['chat_id'], data['chat_id'])
    bot.send_message(data['chat_id'], 'Ваша оплата прошла успешно. Ваш код:')
    bot.send_message(data['chat_id'], '%s' % data['enter_code'])
    user.status = CacheUser.SUCCESS
    user.enter_code = data['enter_code']
    return json.dumps({'status': 'OK'})


@app.route('/send/fail/', methods=['POST'])
@check_auth
def send_fail():
    data = json.loads(request.data.decode('utf-8'))
    bot.send_message(data['chat_id'], 'Ваша оплата не прошла.')
    return json.dumps({'status': 'OK'})


def set_webhook():
    time.sleep(2)
    if bot.set_webhook(url=HOST + TOKEN):
        logging.info('WebHook was set')
    else:
        logging.info('WebHook wasnt set')


if __name__ == '__main__':
    logging.basicConfig(filename=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs/bot.log'),
                        level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    set_webhook()
    app.run(host='0.0.0.0',
            port=PORT,
            debug=True)
