import logging
import os

import yaml
from telegram.ext import CommandHandler, RegexHandler, Updater

logger = logging.getLogger()


# def save_chat_id(self, update):
#     if not self.has_chat_id():
#         network.save_telegram_chat_id(update.message.chat_id)
#         logger.debug('Set Telegram chat_id %s', update.message.chat_id)

def debug(bot, update):
    logger.debug('Received Telegram bot message: {0}'.format(
        update.message.text))

def valid_chat_id(bot, update):
    return all([
        'telegram_chat_id' in self.config,
        update.message.chat_id != self.config['telegram_chat_id']
    ])


@valid_chat_id
def help(bot, update):
    bot.sendMessage(
        bot.chat_id,
        parse_mode='Markdown',
        text=(
            '/status: Request status'
            '\n/disable: Disable alarm'
            '\n/enable: Enable alarm'
            '\n/photo: Take a photo'
            '\n/gif: Take a gif\n'
        ),
        timeout=10
    )

@valid_chat_id
def status(bot, update):
    bot.sendMessage(
        update.chat_id,
        parse_mode='Markdown',
        text=network.state.generate_status_text(),
        timeout=10
    )


@valid_chat_id
def disable(bot, update):
    network.state.update_state('disabled')


@valid_chat_id
def enable(bot, update):
    network.state.update_state('disarmed')


@valid_chat_id
def photo(bot, update):
    photo = camera.take_photo()
    bot.send_file(photo)


@valid_chat_id
def gif(bot, update):
    gif = camera.take_gif()
    bot.send_file(gif)


def error_callback(self, update, error):
    logger.error('Update "{0}" caused error "{1}"'.format(update, error))

class TelegramBot(object):
    """Telegram bot wrapper."""

    def __init__(self, token, chat_id=None):
        # self.data_file = None
        self._config = None
        self._chat_id = chat_id

        # try:
        #     self.updater = Updater(token)
        #     dp = self.updater.dispatcher
        #     dp.add_handler(RegexHandler('.*', self.save_chat_id), group=1)
        #     dp.add_handler(RegexHandler('.*', self.debug), group=2)
        #     dp.add_handler(CommandHandler("help", self.help), group=3)
        #     dp.add_handler(CommandHandler("status", self.status), group=3)
        #     dp.add_handler(CommandHandler("disable", self.disable), group=3)
        #     dp.add_handler(CommandHandler("enable", self.enable), group=3)
        #     dp.add_handler(CommandHandler("photo", self.photo), group=3)
        #     dp.add_handler(CommandHandler("gif", self.gif), group=3)
        #     dp.add_error_handler(self.error_callback)
        #     # updater.start_polling(timeout=10)
        # except Exception:
        #     logger.exception('Updater failed to start: ')
        # else:
        #     logger.info("Telegram bot running")

    @property
    def chat_id(self):
        if self._chat_id is None:
            chat_id = ''

    @property
    def config(self):
        if self._config is None:
            self._config = from_object(app_config)
        return self._config

    def has_chat_id(self):
        return any([
            'telegram_chat_id' in self.config.saved_data,
            self.config.saved_data['telegram_chat_id']
        ])

    def save_telegram_chat_id(self, chat_id):
        """Saves the telegram chat ID to the data file."""
        try:
            # Use a lock here?
            self.config['telegram_chat_id'] = chat_id
            with open(self.config, 'w') as f:
                yaml.dump({'telegram_chat_id': chat_id},
                          f, default_flow_style=False)
        except Exception as exc:
            logger.error(
                'Failed to write state file %s: %s',
                self.config,
                exc
            )
        else:
            logger.debug('State file written: %s', self.config)

    def send_message(self, message):
        try:
            self.updater.sendMessage(
                chat_id=self.config['telegram_chat_id'],
                parse_mode='Markdown',
                text=message,
                timeout=10
            )
        except Exception as e:
            logger.error(
                'Telegram failed to send message "%s", exc: %s',
                message,
                e
            )
        else:
            logger.info('Telegram message Sent: "%s"', message)

    def send_file(self, file_path):
        _, file_extension = os.path.splitext(file_path)
        try:
            with open(file_path, 'rb') as data:
                if file_extension == '.mp4':
                    self.updater.sendVideo(
                        chat_id=self.config['telegram_chat_id'],
                        video=data,
                        timeout=30
                    )
                elif file_extension == '.gif':
                    self.updater.sendDocument(
                        chat_id=self.config['telegram_chat_id'],
                        document=data,
                        timeout=30
                    )
                elif file_extension == '.jpeg':
                    self.updater.sendPhoto(
                        chat_id=self.config['telegram_chat_id'],
                        photo=data,
                        timeout=10
                    )
                else:
                    logger.error('Uknown file not sent: %s', file_path)
        except Exception as exc:
            logger.error(
                'Telegram failed to send file %s, exc: %s',
                file_path,
                exc
            )
        else:
            logger.info('Telegram file sent: %s', file_path)
