import logging
import os

from telebot import types as telebot_types


# Used to trace events that span the handling of a message within a chat
class MessageFormatter(logging.Formatter):
    def format(self, record):
        if hasattr(record, "chat_id"):
            record.chat_id = record.chat_id
        # Note: this should never happen, but if it does, we'll just set the chat ID and message ID to N/A
        else:
            record.chat_id = "N/A"

        if hasattr(record, "message_id"):
            record.message_id = record.message_id
        # Note: this should never happen, but if it does, we'll just set the chat ID and message ID to N/A
        else:
            record.message_id = "N/A"

        return super().format(record)


# Used to log events that span a request on our server
class RequestFormatter(logging.Formatter):
    def format(self, record):
        if hasattr(record, "request_method"):
            record.request_method = record.request_method
        # Note: this should never happen, but if it does, we'll just set the request method and URL to N/A
        else:
            record.request_method = "N/A"
        if hasattr(record, "request_url"):
            record.request_url = record.request_url
        # Note: this should never happen, but if it does, we'll just set the request method and URL to N/A
        else:
            record.request_url = "N/A"
        return super().format(record)


class Logger:
    logger: logging.Logger
    handler: logging.Handler

    def __init__(self, log_path=None, debug=False):
        """
        Initialize a new Log instance
        - log_path - where to send output. If `None` logs are sent to the console
        - debug - whether to set debug level
        """

        # Create the logger
        logger = logging.getLogger(__name__)

        # Set our debug mode
        if debug:
            logging.basicConfig(level=logging.DEBUG)
            # Hide debug logs from other libraries
            logging.getLogger("asyncio").setLevel(logging.WARNING)
            logging.getLogger("aiosqlite").setLevel(logging.WARNING)
        else:
            logging.basicConfig(level=logging.INFO)

        # Set where to send logs
        if log_path is not None and log_path.strip() != "":
            # Create parent directories if they don't exist
            log_path = log_path.strip()
            log_dir = os.path.dirname(log_path)
            os.makedirs(log_dir, exist_ok=True)
            self.handler = logging.FileHandler(log_path)
        else:
            self.handler = logging.StreamHandler()

        if logger.hasHandlers():
            logger.handlers.clear()
        logger.addHandler(self.handler)

        self.logger = logger

    def get_message_span(self, message: telebot_types.Message):
        # Set the log formatter
        formatter = MessageFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(chat_id)s - %(message_id)s - %(message)s"
        )
        self.handler.setFormatter(formatter)
        return MessageSpan(self, message.chat.id, message.message_id)

    def get_request_span(self, request_method, request_url):
        # Set the log formatter
        formatter = RequestFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(request_method)s - %(request_url)s - %(message)s"
        )
        self.handler.setFormatter(formatter)
        return RequestSpan(self, request_method, request_url)

    def warn(
        self,
        message,
        chat_id=None,
        message_id=None,
        request_method=None,
        request_url=None,
    ):
        extra = {}
        if chat_id:
            extra["chat_id"] = chat_id
        if message_id:
            extra["message_id"] = message_id
        if request_method:
            extra["request_method"] = request_method
        if request_url:
            extra["request_url"] = request_url
        self.logger.warning(message, extra=extra)

    def debug(
        self,
        message,
        chat_id=None,
        message_id=None,
        request_method=None,
        request_url=None,
    ):
        extra = {}
        if chat_id:
            extra["chat_id"] = chat_id
        if message_id:
            extra["message_id"] = message_id
        if request_method:
            extra["request_method"] = request_method
        if request_url:
            extra["request_url"] = request_url
        self.logger.debug(message, extra=extra)

    def info(
        self,
        message,
        chat_id=None,
        message_id=None,
        request_method=None,
        request_url=None,
    ):
        extra = {}
        if chat_id:
            extra["chat_id"] = chat_id
        if message_id:
            extra["message_id"] = message_id
        if request_method:
            extra["request_method"] = request_method
        if request_url:
            extra["request_url"] = request_url
        self.logger.info(message, extra=extra)

    def error(
        self,
        message,
        chat_id=None,
        message_id=None,
        request_method=None,
        request_url=None,
    ):
        extras = {}
        if chat_id:
            extras["chat_id"] = chat_id
        if message_id:
            extras["message_id"] = message_id
        if request_method:
            extras["request_method"] = request_method
        if request_url:
            extras["request_url"] = request_url
        self.logger.error(message, extra=extras)


class MessageSpan:
    def __init__(self, logger, chat_id, message_id):
        self.logger = logger
        self.chat_id = chat_id
        self.message_id = message_id

    def warn(self, message):
        self.logger.warn(message, chat_id=self.chat_id, message_id=self.message_id)

    def debug(self, message):
        self.logger.debug(message, chat_id=self.chat_id, message_id=self.message_id)

    def info(self, message):
        self.logger.info(message, chat_id=self.chat_id, message_id=self.message_id)

    def error(self, message):
        self.logger.error(message, chat_id=self.chat_id, message_id=self.message_id)


class RequestSpan:
    def __init__(self, logger, request_method, request_url):
        self.logger = logger
        self.request_method = request_method
        self.request_url = request_url

    def warn(self, message):
        self.logger.warn(
            message, request_method=self.request_method, request_url=self.request_url
        )

    def debug(self, message):
        self.logger.debug(
            message, request_method=self.request_method, request_url=self.request_url
        )

    def info(self, message):
        self.logger.info(
            message, request_method=self.request_method, request_url=self.request_url
        )

    def error(self, message):
        self.logger.error(
            message, request_method=self.request_method, request_url=self.request_url
        )
